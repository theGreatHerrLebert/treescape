# Changelog

All notable changes to treescape are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] — 2026-04-28

The metadata-driven-styling release. v0.2 shipped explicit dict-based `.color_tips({...})` and rectangular-only `.highlight_clade(...)`. v0.3 makes those automatic from joined metadata, adds continuous coloring, and lifts the circular-layout `NotImplementedError` for `.highlight_clade` via annular sectors. Five EVIDENT claims added or extended; 187 / 31 / 8 oracle suite green; cargo workspace 46 + 11 green.

### Phase 1 — `join_metadata` data-binding (polars-only)

- **`TreePlot.join_metadata(df, on=...)`** — chainable. Validates a `polars.DataFrame` against the tree's tip universe and stores per-tip rows for downstream coloring. Loud on every failure mode: extra rows whose `on=` value is not a tip raise `ValueError` with the offending count and first 5 names; duplicate `on=` values raise; chained-join column-name collisions raise (silent overwrite is the "which frame won?" failure mode that's hardest to debug). Empty frames are legal and produce all-`None` metadata for every tip with no warning.
- **Polars-only.** The plan considered dual-support and a `__dataframe__` interchange compromise; both rejected to keep maintenance flat. pandas users convert via `pl.from_pandas(df)`. One supported frame type, one error surface. Reconsider in a v0.x point release if user-reach demands.
- **Storage scope: Python-side, no FFI.** The joined frame is held on the `TreePlot` instance; `_metadata_for(tip_name)` returns a plain Python dict (column dtypes preserved as Python scalars). Phase 2 metadata-driven coloring resolves to `{tip_name: color}` dicts on the Python side and reuses the v0.2 styled-SVG path. The Rust `treescape-core` crate is unchanged. Trade-off disclosed: practical-N for metadata-driven plots is capped at Python dict overhead, not the SoA Rust core's actual capacity. Fine for v0.3's expected scale (≤10k tips × ≤10 columns); revisit in v0.4 with a columnar-FFI variant if the use case shows up.
- **New EVIDENT claim** `treescape-metadata-join-roundtrip` (ci-tier): every tip is queryable post-join; tips with no row return all-`None`; extra rows raise; duplicates raise; chained joins add columns and column-name collisions raise. v0.3 oracles the Python reference against itself (round-trip + explicit failure-mode tests) since there is no Rust port.
- **`treescape-reference/src/treescape_reference/metadata.py`** is the convention owner. Synthetic CSV fixtures at `tests/fixtures/metadata/small/{two_tip,balanced_4,unbalanced_5}.csv` — each chosen so at least one MRCA is monophyletic-by-`clade` and at least one is paraphyletic, giving Phase 2's branch-coloring claim both code paths from one fixture.
- **`polars>=1.0`** added to `treescape-reference` and `treescape` runtime deps.

### Phase 2 — metadata-driven branch & tip coloring

#### Discrete (categorical palette)

- **`TreePlot.color_tips_by(column, palette=...)`** maps a discrete metadata column through `palette` (defaults to **Tableau-10** in tree tip-order). User palettes must cover every observed non-`None` value; missing entries raise. More than 10 observed values with the default palette raise — no cycling, because cycling silently makes unrelated categories share color. Round-trip claim: `treescape-color-tips-by-discrete-roundtrip` (ci-tier) — produces the same per-tip colors as the equivalent explicit `.color_tips({...})` call.
- **`TreePlot.color_branches_by(column, palette=...)`** colors rectangular internal branches by **monophyly**: a branch is colored iff every descendant tip shares one non-missing value for `column`. Mixed or missing values leave the default branch color and emit `TreescapeStyleWarning` naming the branch and column. Diverges from ggtree's silent fallback; surfaces miscoloring instead of hiding. Standard `warnings.filterwarnings(...)` opts out — no custom toggle. Claim: `treescape-color-branches-by-monophyly` (ci-tier) — asserts both color *and* warning (or its absence on the monophyletic path) via `pytest.warns` / `warnings.catch_warnings`.
- The discrete EVIDENT claim was deliberately split into a tips claim and a branches-by-monophyly claim. Collapsing them was the "claim overstatement" anti-pattern v0.1 and v0.2 round-1 reviews caught — the tip path and the branch path exercise different code.
- Terminal branches are out of scope for v0.3's monophyly claim. They remain default-colored until a separate terminal-branch styling API lands.

#### Continuous (gradient)

- **Default colormap: viridis.** treescape ships its own pinned 11-keystop viridis LUT in `packages/treescape/src/treescape/plot.py::_VIRIDIS_LUT` with linear RGB interpolation between stops. Visually faithful to matplotlib's full 256-stop viridis; **byte-determinism is exact, full-256-stop fidelity is not**. Endpoints `#440154` at `t=0` and `#fde725` at `t=1`. A LUT change is a treescape-version-level break that regenerates golden bytes — track it explicitly in CHANGELOG.
- **API:** `color_tips_by(column, cmap=, vmin=, vmax=)` and `color_branches_by(column, cmap=, vmin=, vmax=)`. `cmap` accepts a string name (built-ins: `"viridis"`) or a callable `(t: float) -> "#rrggbb"`. Passing both `palette=` and `cmap=` raises `ValueError`. Auto-detection: if neither is given, all-numeric observed values (excluding `bool`) → continuous; otherwise → discrete.
- **Range:** `vmin` / `vmax` default to the column's observed min/max across the tree's tip universe — so tip and branch coloring on the same column share a coherent scale by construction. Values outside `[vmin, vmax]` are clamped, not extrapolated. **Degenerate range** (`vmin == vmax`, or all values equal) deterministically maps every value to `t = 0.5` (colormap midpoint) — no divide-by-zero.
- **Branch coloring (numeric):** each non-tip branch is colored by the **mean** of descendant tips' non-missing values, mapped through `cmap`. Subtrees with no observed values keep the default color **silently** — no warning, since "no data" is not a paraphyletic miscoloring (contrast with the discrete monophyly path, which warns on mixed/missing).
- **New EVIDENT claim** `treescape-color-by-continuous-determinism` (ci-tier, property-style): same column values + same `cmap` + same `(vmin, vmax)` → byte-identical SVG. 10 tests covering byte-determinism on tips and branches, default-cmap-is-viridis with LUT endpoints, vmin/vmax pin range and clamp outliers, degenerate range → midpoint, callable cmap honored, palette+cmap conflict raises, unknown cmap name raises, subtree-with-no-data is silent, auto-detect == explicit `cmap="viridis"`.

### Phase 3 — circular clade highlighting (annular sectors)

- **`TreePlot.layout("circular").highlight_clade(...)`** is now supported. The v0.2 `NotImplementedError` for circular highlights is lifted; v0.2 styled SVG bytes are unchanged.
- **New scene type: `AnnularSector(cx, cy, r_inner, r_outer, theta_min, theta_max, fill)`** in both `treescape-reference/scene.py` and `treescape-core/layout/scene.rs`. Coordinates in pixels (post-projection), matching `Rect`. Emitted before `Line`/`Arc`/`Text` so highlights render behind branches and labels — same z-order as the rectangular `Rect` highlight.
- **Geometry:** `r_inner = mrca_r * px_per_x` (MRCA's branch point); `r_outer = max_r * px_per_x + label_offset + max_label_px` (every highlight extends to the same outer radius — the polar analogue of v0.2's "rectangle to canvas right edge"). `theta_min`, `theta_max` are the min/max layout tip angles in `clade_tips(MRCA)` (internal-node angles do not bound the sector — only tip angles, matching the rectangular row-span convention).
- **MRCA == root → `ValueError`.** A clade whose MRCA is the root covers every tip — the highlight would cover the whole canvas (visually meaningless, blocks every branch and label). Loud-rejected at `to_svg`-time. Wrap-split paths are dead code under v0.3's `start_angle = π/2`, `sweep = 2π` convention; a fan layout (`sweep_total < 2π`) reopens the wrap question.
- **SVG emit:** `<path d="M ... L ... A ... L ... A ... Z" fill="...">`. Outer arc uses `sweep_flag = 0` (CCW visually under our SVG y-flip — same convention as the existing `Arc` spine); inner arc returns with `sweep_flag = 1`. `large_arc = 1` iff `theta_max − theta_min > π`. Float formatting matches the existing `Arc` renderer (`{:.4}` trim trailing zeros) — keeps Rust↔Python ref byte parity.
- **Connector:** new `render_circular_styled_svg(tree, opts, highlights)` PyO3 function. Maps `Result::Err` containing `"MRCA == root"` to `PyValueError`; other errors map to `PyRuntimeError`.
- **EVIDENT claim** `treescape-styling-determinism` is **extended**, not replaced. Byte-determinism property carries over unchanged. Additional property: an `AnnularSector`'s `[theta_min, theta_max]` equals the min/max layout tip angles in the clade. Rectangular↔circular shape equivalence under the polar transform is **not** claimed — each layout is byte-deterministic in its own conventions, no cross-shape parity. 8 new tests added (2× repeated render parity, 2× golden snapshot, 2× Rust↔Python ref byte parity, 1× MRCA == root raise at both ref and connector layers, 1× angular-bounds property). Two new goldens checked in: `tests/fixtures/golden/{balanced_4,unbalanced_5}_styled_circular.svg`.
- **Other circular styling features remain `NotImplementedError`.** v0.3 Phase 3 is highlights-only per the plan. The circular-path `NotImplementedError` is now per-feature: it names which of `.color_tips` / `.color_tips_by`, `.color_branches_by`, `.scale_bar`, `.support_labels` is in use, instead of catching all of them with one message. Each is a natural follow-up; not in v0.3 scope.

### Bonus rectangular grammar (not in the v0.3 plan, accepted)

- **`TreePlot.scale_bar(length, label=None)`** — draws a branch-length scale bar below rectangular trees. Length validated `> 0`. Raises `NotImplementedError` on `.layout("circular")` since circular has no horizontal axis to anchor a scale bar to.
- **`TreePlot.support_labels(min_value=None)`** — renders internal node names as support labels with optional numeric threshold filtering. Raises `NotImplementedError` on `.layout("circular")` for now (circular extension is a follow-up).
- The connector signature for `render_rectangular_styled_svg` grew to thread `branch_colors`, `scale_bar`, `support_labels`, `support_min`. v0.2 byte-determinism preserved on existing fixtures.

### EVIDENT manifest

- **16 claims pinned, all green.** v0.2 baseline was 11; v0.3 adds 4 new (`treescape-metadata-join-roundtrip`, `treescape-color-tips-by-discrete-roundtrip`, `treescape-color-branches-by-monophyly`, `treescape-color-by-continuous-determinism`) and extends `treescape-styling-determinism` to the circular path.

### Backwards compatibility

- **v0.2 `.color_tips({...})` and rectangular `.highlight_clade(...)` work unchanged.** v0.3 adds new entry points; it does not break or rename existing ones.
- **`treescape-svg-determinism` and `treescape-styling-determinism` byte-determinism** holds over identical bytes for fixtures that don't use metadata or circular highlights. Golden SVGs from v0.2 were not regenerated.
- **`polars>=1.0`** is a new runtime dep — see Phase 1.

### Cuts deferred to v0.4+

- **Circular `.color_tips` / `.color_tips_by` / `.color_branches_by` / `.support_labels`.** Each is a natural extension of the AnnularSector path geometry / Text fill / Line stroke pipelines but needs its own convention pass and oracle.
- **`.scale_bar` on circular layouts.** Probably belongs as a calibration ring at a fixed radius rather than a horizontal bar; design-decision deferred.
- **Branch-stroke width by metadata, node shape styling, terminal-branch coloring.**
- **Nexus and PhyloXML parsers, PDF export, `treescape-cli`, kerning + non-Latin shaping.** Same v0.4+ list as v0.2 deferred.
- **GPU label collision avoidance, force-directed unrooted layout.** v0.4+/v0.5+.
- **Columnar-FFI variant for metadata-driven coloring at >50k tips × dense metadata.** v0.3 ships Python-dict-side; revisit when a real-world fixture pushes against the budget.

## [0.2.0] — 2026-04-28

### Fixes (review round 1, post-phase-3)

- **`render_circular` honors `CircularSceneOptions.start_angle` / `sweep_total`.** Previously both `treescape_render::render_circular` and `build_circular_scene_` called `circular_layout(tree)` with hardcoded defaults, so a fan request via the connector (`CircularSceneOptions(sweep_total=π)`) silently rendered a full circle. Both now route through `circular_layout_with(tree, opts.start_angle, opts.sweep_total)`. Default behavior unchanged.
- **`TreePlot.options(...)` now updates the circular option struct.** It previously only mutated `_scene_opts`, so `.layout("circular").options(font_size=24, padding=…)` was a silent no-op on the circular render path. Shared knobs (`padding`, `font_size`, `label_offset`, `stroke_width`) and `px_per_x → px_per_r` are applied to both option structs; `start_angle` / `sweep_total` are preserved across reconstruction.
- **Chained `.options()` calls preserve prior overrides.** The reconstruction step previously hardcoded `label_offset=4.0` and `stroke_width=1.0`, so `.options(label_offset=12).options(font_size=18)` reset `label_offset` back to default. Added `#[getter]` for `label_offset` and `stroke_width` on `PySceneOptions` and `PyCircularSceneOptions`; Python now reads from the existing struct instead of hardcoding.
- **`docs/conventions.md` tip-angle formula sign.** The body wrote `θ_i = start_angle + (i / N) · sweep_total` while implementation, tests, and the note immediately below it use `−` to encode the clockwise sweep. Sign corrected; forward pointer to *Sweep direction* added so the minus sign isn't a surprise.
- **`tests/oracle/test_text_width.py` no longer fails collection without the connector.** Hard `from treescape_connector.py_render import …` replaced with `try/except ImportError → @pytest.mark.skipif`, matching `test_styling_determinism.py` / `test_svg_determinism.py`.

### Phase 3 — clade highlighting + per-tip color overrides

- **`TreePlot.highlight_clade(tips=[...], color=, alpha=)`** — chainable. The MRCA of the named tips is computed and a translucent rectangle is drawn behind branches and labels, spanning from the MRCA's branch point to the canvas right edge, covering all rows in the clade.
- **`TreePlot.color_tips({name: color, ...})`** — chainable. Overrides per-tip label color; tips not in the map keep `SceneOptions.label_color`.
- Color specs accept `"#rrggbb"`, `"#rrggbbaa"`, `(r, g, b)`, or `(r, g, b, a)` (0–255 ints). Validated up front by `_parse_color`.
- **New EVIDENT claim** `treescape-styling-determinism` (ci-tier, property-style): same input + same styling → byte-identical SVG, across 4 fixtures × 3 modes (repeated render, golden snapshot, Rust↔Python ref bytes) = 12 tests.
- New scene types: `Rect(x, y, width, height, fill)` in both Python and Rust, emitted as `<rect>` before lines/arcs/text so highlights render behind branches.
- New helpers: `find_mrca(tree, tip_names)` and `clade_tips(tree, mrca)` in both `treescape-reference` and `treescape-core`. Mismatched / missing tip names raise cleanly.
- Rust scene builder: `build_rectangular_scene_with_style(...)` extends `..._with_measurer` with a `&StyleSpec` parameter; the previously-public `_with_measurer` now delegates with an empty `StyleSpec` so existing rectangular SVG bytes are unchanged.
- Python ref: `build_rectangular_scene(tree, opts, measure, style=None)` — same shape, default `None` style preserves prior bytes.
- Connector: new `render_rectangular_styled_svg(tree, opts, highlights, tip_colors)` PyO3 function.
- **Cuts deferred to v0.3:** circular layout + clade highlighting (raises `NotImplementedError` cleanly); metadata-driven color (`color_branches_by(metadata_col=...)` requires the `join_metadata` API which is a separate v0.2 deliverable); branch-color overrides; node shape styling.

### Phase 2 — circular layout (part 2: rendering + oracles)

- **Circular SVG rendering.** New `Arc` scene-graph item (Python + Rust) emitted as SVG `<path d="M ... A r r 0 large sweep ...">`; new `rotation_deg` field on `Text` emitted as `transform="rotate(...)"`. The circular scene builder combines radial branch lines, arc spines (one per internal node with ≥2 children, at radius=parent.r), and rotated tip labels with hemisphere-flipped anchor so labels read outward.
- **`TreePlot.layout("circular")`** is now a supported user-facing layout. `treescape_connector.py_render` exposes `CircularSceneOptions` and `render_circular_svg`.
- **`treescape-svg-determinism`** claim extended to circular: 12 new tests across 4 fixtures × {repeated, golden snapshot, Rust↔Python ref bytes}. Goldens checked in at `tests/fixtures/golden/<fixture>_circular.svg`.
- **`treescape-circular-layout-vs-ete3`** (ci-tier) — green. ete3 doesn't expose circular coords (Qt-bound); same indirect strategy as the rectangular ete3 oracle works here too: r ↔ `ete3.get_distance`, θ derived from ete3's `iter_leaves()` pre-order index applied to treescape's convention formula.
- **`treescape-circular-layout-vs-ggtree`** (release-tier) — green. As predicted, the first end-to-end run surfaced two real divergences (documented in `docs/conventions.md`):
  - ggtree's tip *i* (1-based) sits at `i·2π/N` sweeping **CCW**, last tip at 3 o'clock. treescape uses `π/2 − i·2π/N` sweeping **CW**, first tip at 12 o'clock. Per-tip transform: `θ_ggtree = 2π/N + π/2 − θ_ours` (mod 2π).
  - ggtree uses linear mean for internal-node angle; treescape uses wrap-aware vector mean. Diverges only on diametrically-opposed children. Oracle test sidesteps by comparing tips only.
- `workflow/scripts/oracle_ggtree.R` gains a `--circular` flag that emits `(node, r, θ)` for the new oracle test.

### Phase 2 — circular layout (part 1: coordinates)

- **`circular_layout(tree)`** in `treescape-reference` and `treescape-core` — polar `(r, θ)` per node. `r` is cumulative branch length (matching rectangular's x); tip θ is `start_angle − (i / N) · sweep_total` for tip `i` in pre-order leaf traversal — clockwise from `start_angle`. Internal-node θ uses the wrap-aware vector mean (`atan2` of summed unit vectors) so children straddling the 0/2π boundary still produce a sane bisector.
- **Defaults:** `start_angle = π/2` (12 o'clock), `sweep_total = 2π` (full circle). Configurable for fan layouts (`sweep_total = π` etc).
- **Two new EVIDENT claims** pinned: `treescape-circular-layout-vs-ete3` (ci) and `treescape-circular-layout-vs-ggtree` (release). Oracle tests land in part 2 alongside the rendering. Per the v0.1 cadence, claims pinned before code.
- **Rust↔Python parity** under `treescape-layout-rust-vs-reference` extends to circular: 4 fixtures × `(r, θ)` per tip within `1e-9`.
- **Convention doc:** `docs/conventions.md` gains a "treescape conventions (v0.2, circular layout)" section locking radius rule, tip-θ formula, internal-node arc-aware mean, and the SVG y-flip Cartesian projection.
- **TreePlot.layout("circular")** still raises `NotImplementedError` — user-facing rendering lands in part 2.

### Phase 1 — fontdue tip-label widths

- **Real glyph metrics for tip-label widths.** v0.1 estimated label width as `N_chars * font_size * 0.6` (a monospace approximation that was wrong for proportional fonts). v0.2 replaces it with fontdue advance-width measurement of the bundled DejaVu Sans on the Rust side and `fontTools` HMTX read on the Python reference side. Both produce floating-point-identical widths across the test battery.
- **New EVIDENT claim** `treescape-text-width-vs-fontdue` (ci-tier): Rust widths agree with the Python reference within 0.5 px on a 14-string × 5-size battery (70 cases).
- **API change:** `SceneOptions(avg_glyph_width=...)` is no longer accepted by the Python API; the Rust `CoreSceneOptions.avg_glyph_width` field is retained for the legacy `build_rectangular_scene` (no-measurer) fallback only. The user-facing `treescape-render` and PyO3 paths use fontdue unconditionally.
- **Canvas widths shifted.** All four golden SVG fixtures and `assets/primates.svg` regenerated; byte-determinism still holds across runs.
- **`scripts/regen_assets.py`** added — canonical `assets/primates.svg` regeneration.
- **`fonttools>=4.50`** added to `treescape-reference` runtime deps.
- The bundled `DejaVuSans.ttf` is now shipped in both `treescape-render/src/fonts/` and `packages/treescape-reference/src/treescape_reference/fonts/` so the Python wheel is self-contained.

## [0.1.0] — 2026-04-28

The first shippable cut. Tight v0.1 scope: load Newick, render a rectangular phylogram with tip labels, save deterministic SVG.

### Added

- **Newick parsing/writing** in `treescape-core` (hand-rolled, iterative). Handles quoted names, NHX comments (consumed in v0.1), negative branch lengths, and trifurcation roots. Strict grammar: requires trailing `;`, rejects multiple top-level roots, rejects trailing content after the semicolon.
- **Rectangular layout** with documented conventions (x = cumulative branch length, tip y = pre-order leaf index, internal y = mean of immediate children's y).
- **Ladderization** with both ascending and descending orders. The descending tie-break matches ete3's `direction=1` behavior exactly (sort key `(-size, -original_position)`).
- **Pure-Rust deterministic SVG renderer** in `treescape-render`. Sorted attributes, fixed `{:.4}` float formatting, no timestamps. Bundles DejaVu Sans for downstream font measurement.
- **PyO3 bindings** in `treescape-connector` mirroring the rustims layout (one cdylib, four `wrap_pymodule!` submodules registered in `sys.modules`).
- **`TreePlot` grammar** in the user-facing `treescape` Python package. v0.1 surface is intentionally tight: load, layout, tips, options, save.
- **`treescape-reference` Python package** — slow, readable parser/layout/renderer that serves as the EVIDENT oracle for the Rust core. Designed to be PyPI-publishable so users can verify claims independently.
- **EVIDENT trust manifest** at `evident.yaml` with eight claims pinned before implementation:
  - `treescape-newick-roundtrip` (ci): Biopython parity + own-roundtrip
  - `treescape-layout-rust-vs-reference` (ci): Rust matches Python reference within `1e-9`
  - `treescape-layout-vs-ete3` (ci): ete3 traversal + distance parity within `1e-6`
  - `treescape-layout-vs-biopython` (ci): Biopython.Phylo.draw layout parity within `1e-6` (Biopython's own functions extracted via `inspect`)
  - `treescape-layout-vs-ggtree` (release): R + ggtree parity within `1e-4`
  - `treescape-ladderize-order` (ci): tip order matches ete3 `direction=0` and `direction=1`
  - `treescape-svg-determinism` (ci): byte-identical output across runs; Rust↔Python reference byte parity
  - `treescape-tip-count-invariant` (ci): hypothesis property — N tips → N tip glyphs, all coords within canvas

### Trust contract

Claim runners live at `tests/oracle/test_*.py`. The release-tier `ggtree` runner is gated to the image at `workflow/Dockerfile.evident-release` and runs in CI only on tag pushes.

### Known v0.1 limitations (deferred to v0.2)

- Circular and radial layouts.
- PDF export (SVG only).
- Clade highlighting.
- Branch- and node-style mappings to metadata. v0.1 supports `tips(label="name")` only.
- Real fontdue-measured tip-label widths. v0.1 uses `avg_glyph_width=0.6` monospace approximation, sufficient for canvas-bounds invariant but not for aggressive collision avoidance.
- Nexus and PhyloXML parsers.
- `treescape-cli` and a `treeplot` console entry point.
- Polars/pandas dual-support; the metadata API is v0.2.

### Bundled font

DejaVu Sans (Bitstream Vera Fonts License) is bundled at `treescape-render/src/fonts/DejaVuSans.ttf`. License notice alongside.
