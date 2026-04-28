# v0.3 plan

Working plan for the next minor version. Mirrors the v0.2 cadence (per the saved feedback memory): tight scope, EVIDENT claims pinned **before** the code, Python reference first then Rust port, external review at the end of each phase.

## Theme

**Make styling data-driven and finish the v0.2 NotImplementedError gates.** v0.2 added explicit dict-based `.color_tips({name: color})` and rectangular-only `.highlight_clade(...)`. v0.3 makes those automatic from metadata (so users don't hand-build dicts) and lifts the rectangular-only restriction.

## Proposed trio (in implementation order)

### Phase 1 — `join_metadata` data-binding API

The foundational piece. Everything else in v0.3 (color-by-column, label-by-column) depends on it.

```python
import polars as pl
TreePlot("tree.nwk").join_metadata(
    pl.DataFrame({"tip": [...], "clade": [...], "support": [...]}),
    on="tip",
)
```

- Validation: every tip in the tree has at most one row; tips with no row get `None` for every metadata column. Extra rows raise (loud failure on typos).
- Storage: keep the joined frame on `TreePlot`; access via `_metadata_for(tip_name)` internal helper. No columnar lookups crossing the Python/Rust FFI for v0.3 — metadata-driven coloring resolves to a `{tip_name: color}` dict on the Python side and uses the existing `color_tips` / `color_branches` paths.
- **Trade-off disclosed:** this caps practical-N for metadata-driven plots at the Python dict overhead, not the Rust SoA core's actual capacity. Fine for v0.3's expected scale (≤10k tips × ≤10 columns); a user with 50k+ tips × dense metadata would feel this. Revisit in v0.4 with a columnar-FFI variant if the use case shows up.
- **Test fixtures:** new `tests/fixtures/metadata/<tree_id>.csv` files alongside the existing tree fixtures. Synthetic only for v0.3 — values picked to exercise both monophyletic-by-column and paraphyletic-by-column subtree shapes (so Phase 2's branch-coloring claim has both code paths covered). Real-biology metadata waits until a use case justifies the citation/license footprint.
- **New EVIDENT claim** `treescape-metadata-join-roundtrip` (ci-tier): joining a frame and then querying every tip returns the same row data; tips not in the frame return all-None; extra rows in the frame raise.

**Decision (locked):** **polars-only**. The original plan considered dual-support (and a polars-primary/pandas-via-interchange compromise was tabled), but the user pinned polars-only — one supported path, one set of tests, one error surface. pandas users coming from the wider phylogenetics ecosystem can convert with `pl.from_pandas(df)`; that one-liner stays out of treescape's surface area. Reconsider in a v0.x point release if the user-reach gap shows up in issues.

### Phase 2 — metadata-driven branch & tip coloring

```python
plot = (
    TreePlot("tree.nwk")
    .join_metadata(df, on="tip")
    .color_tips_by("clade")           # discrete column → categorical palette
    .color_branches_by("support")     # numeric column → gradient
)
```

- **Discrete column → categorical palette.** Default palette: 10-color qualitative (Tableau-10 or matplotlib's `tab10`). User can pass `palette={"a_clade": "#xxx", ...}` for full control.
- **Numeric column → continuous gradient.** Default: viridis (perceptually uniform, colorblind-safe). User can pass `cmap="RdBu"` / `cmap=callable`. Range auto-detected from the column; user can pin via `vmin=`, `vmax=`.
- **Branch coloring:** for each non-tip branch, color is the metadata value of the **child tip subtree** if the clade is monophyletic by that column. Otherwise fall back to default branch color *and emit a `TreescapeStyleWarning`* (a `UserWarning` subclass) naming the branch and the column. ggtree fails silent here; v0.3 chooses warn so paraphyletic miscoloring surfaces instead of hiding. The warning is opt-out per Python's standard `warnings.filterwarnings(...)` machinery — no custom toggle.
- **Three new EVIDENT claims** (the discrete claim is split because tips and branches exercise different code paths — collapsing them into one would be the "claim overstatement" anti-pattern that round-1 reviews caught in v0.1 and v0.2):
  - `treescape-color-tips-by-discrete-roundtrip` (ci-tier): a discrete-column → palette map produces the same per-tip colors as the equivalent explicit `.color_tips({...})` call.
  - `treescape-color-branches-by-monophyly` (ci-tier): for each internal branch `X` and discrete column `C`, branch color is `palette[v]` iff every tip in `subtree(X)` has `C = v`; otherwise the default branch color **and a `TreescapeStyleWarning` is raised naming `X` and `C`**. Tested on a tree where one clade is monophyletic by `C` and at least one other clade is paraphyletic — both paths exercised, neither defaulted-into. Test asserts both the color *and* the warning (or its absence on the monophyletic path) via `pytest.warns` / `warnings.catch_warnings`.
  - `treescape-color-by-continuous-determinism` (ci-tier, property-style): same column values + same `cmap` + same range → byte-identical SVG.

### Phase 3 — circular clade highlighting (annular sectors)

Closes the v0.2 `NotImplementedError`. **Doesn't depend on Phase 1 or 2** — if the polars/pandas decision lags, Phase 3 can ship first to keep cadence. Convention decisions to lock up front (mirroring how rectangular highlight bounds were locked in v0.2 Phase 3):

- An annular sector at the clade's MRCA spans `[r_mrca, r_max + label_zone]` radially and `[θ_min, θ_max]` angularly, where `θ_min/max` are the min/max tip angles in the clade and `label_zone` is the radial extent reserved for tip labels.
- **New scene type:** `AnnularSector(cx, cy, r_inner, r_outer, theta_start, theta_end, fill)`. SVG emit as a `<path>` with `M`-`L`-`A`-`L`-`A`-`Z`. Byte-deterministic.
- **Wrap handling:** under v0.3's `start_angle = π/2`, `sweep_total = 2π`, MRCA-based clade convention, a clade whose tip-angle span crosses the wrap point necessarily contains tip 0 and tip N−1 — and the MRCA of the first and last pre-order leaves is the root, so the clade *is* the whole tree. The wrap-split path is dead code under these conventions; raise or no-op when `MRCA == root` (the highlight would cover the whole canvas anyway). If a future fan layout (`sweep_total < 2π`) introduces a real wrap case, revisit then.
- **EVIDENT claim:** extend `treescape-styling-determinism` to the circular path. The byte-determinism property carries over unchanged. Additional property: an annular sector's angular bounds `[θ_min, θ_max]` equal the min/max tip angles in the clade (the polar analogue of v0.2's "rectangle covers all rows in the clade"). The radial bounds use the same `[r_mrca, r_max + label_zone]` convention as the layout itself; rectangular↔circular shape equivalence under the polar transform is *not* claimed — each layout is byte-deterministic in its own conventions, no cross-shape parity.

## Explicitly NOT in v0.3

These are real items, but bundling them dilutes the ship. Pushed to v0.4+:

- **Nexus and PhyloXML parsers.** Self-contained but each is ~1 phase of work. Defer.
- **PDF export.** New emitter sharing the scene graph. Defer.
- **`treescape-cli` / `treeplot` console.** Surface design needs its own pass. Defer.
- **fontdue: kerning + non-Latin shaping.** Wait for a real fixture.
- **Branch-stroke width by metadata, node shape styling.** v0.4.
- **GPU label collision avoidance.** Only matters at >10k tips. v0.4+ when a real-world fixture pushes against the CPU baseline.
- **Force-directed unrooted layout.** v0.5+.

## Cadence (same as v0.1, v0.2)

For each phase:

1. Lock convention decisions in `docs/conventions.md` **before** any code.
2. Pin EVIDENT claim in `evident.yaml` **before** the test exists.
3. Implement the Python reference (`treescape-reference`).
4. Port to Rust (`treescape-core`) and hold to the Python reference within `1e-9` (or per-claim tolerance).
5. Wire through `treescape-connector` (PyO3) and `TreePlot` grammar.
6. External review at end of phase. Address findings before the next phase.
7. Commit + push per phase milestone.

Per the saved feedback memory: recurring v0.1/v0.2 review findings are claim overstatement, undeclared test deps, and silent tolerance bumps. Watch for those.

## Open questions — all resolved

1. **Polars vs pandas for `join_metadata`.** **Polars-only.** pandas users convert via `pl.from_pandas(df)`; out of treescape's surface area.
2. **Default palettes.** **Tableau-10 (discrete), viridis (continuous)** — accepted as written.
3. **Paraphyletic-clade branch-color fallback.** **Default color + `TreescapeStyleWarning`.** Diverges from ggtree's silent fallback; surfaces miscoloring instead of hiding. Standard `warnings.filterwarnings(...)` opts out.
4. **Annular sector wrap handling.** Dead code under v0.3 conventions (start_angle = π/2, sweep = 2π, MRCA-clade) — wrap can only happen when `MRCA == root`, in which case the highlight is the whole canvas. **No-op when `MRCA == root`.** Revisit if a future fan layout (`sweep_total < 2π`) introduces a real wrap case.

All four are locked. Phase 1 can start.

## Success criteria

v0.3 ships when:

- All three phases landed on main (one commit per phase).
- 15 EVIDENT claims green (11 from v0.2 + 4 new: `metadata-join-roundtrip`, `color-tips-by-discrete-roundtrip`, `color-branches-by-monophyly`, `color-by-continuous-determinism`). Phase 3 *extends* `treescape-styling-determinism` rather than adding a claim.
- **Backwards-compat preserved:** v0.2's explicit `.color_tips({...})` and rectangular `.highlight_clade(...)` continue to work unchanged. v0.3 adds new entry points; it does not break or rename existing ones. The `treescape-svg-determinism` and `treescape-styling-determinism` claims continue to pin v0.2 byte-identical output for fixtures that don't use metadata.
- External review of all three phases closed.
- CI green on `main` (rectangular + circular ci-tier) and on the v0.3.0 tag (release-tier ggtree, both rectangular and circular).
- CHANGELOG updated; tag `v0.3.0` pushed.

## Why this trio over alternatives

Considered alternative: **format coverage** (Nexus + PhyloXML + PDF). Each is genuinely useful but they don't compose — three independent ships in one minor doesn't deepen any one capability. The metadata-driven trio composes (phase 1 unlocks 2, phase 2 unlocks rich figures), so the user gets a step-change in what's expressible.

Considered alternative: **CLI + Jupyter + GPU**. Productivity surface, no oracle gotchas. Rejected because (a) CLI design needs its own pass, (b) GPU pays off only at >10k tips and v0.3 isn't motivated by performance, (c) Jupyter display is small enough to do as a v0.3.x point release.
