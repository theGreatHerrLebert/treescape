# v0.4 plan

Working plan for the next minor version. Mirrors the v0.1/v0.2/v0.3 cadence (per the saved feedback memory): tight scope, EVIDENT claims pinned **before** the code, Python reference first then Rust port, external review at the end of each phase.

## Theme

**Complete the styling story.** v0.3 shipped metadata-driven coloring on rectangular layouts, plus circular-layout `highlight_clade` via annular sectors. v0.4 lifts the remaining circular `NotImplementedError` (so `.layout("circular")` reaches feature parity with rectangular for everything except scale-bar geometry), and rounds out branch styling with width-by-metadata and terminal-branch coloring. Result: a publication-ready figure surface — the user can chain features without hitting a "v0.x will lift this" message.

## Proposed trio (in implementation order)

### Phase 1 — circular `.color_tips_by` / `.color_branches_by` / `.color_tips`

The v0.3 plan deferred this with: "each is a natural extension of the AnnularSector path geometry / Text fill / Line stroke pipelines but needs its own convention pass and oracle." Phase 1 does that pass.

```python
TreePlot("tree.nwk").layout("circular").join_metadata(df, on="tip") \
    .color_tips_by("clade") \
    .color_branches_by("support") \
    .save("circular_styled.svg")
```

- **Tip color (Text fill)** — the simpler half. Reuses the same per-Text fill mechanism the rectangular path already has; no new scene primitive, no new convention.
- **Branch color (radial Line stroke)** — convention call: which circular scene primitives carry the branch color?
  - **Locked:** the **radial parent→child `Line`** gets the color. The **arc spine** at the parent's radius (which connects siblings, not parent-to-child) stays at the default stroke color. Mirrors v0.3's rectangular convention where "the horizontal parent→child segment receives the color while the vertical connector spine stays at the default stroke color." A "branch" is a parent-to-child unit; arcs are sibling-connectors.
  - Monophyly logic is unchanged from v0.3 rectangular (every descendant tip shares the same non-missing value → color; otherwise default + `TreescapeStyleWarning`).
  - Continuous (subtree-mean viridis) is also unchanged from v0.3 rectangular logic, just applied to the radial Line.
- **EVIDENT:** extend `treescape-color-tips-by-discrete-roundtrip` and `treescape-color-branches-by-monophyly` and `treescape-color-by-continuous-determinism` to circular layouts (each existing claim's coverage table grows, no new claim ID — same precedent as v0.3 Phase 3 extending `treescape-styling-determinism`). Rust↔Python ref byte parity continues to hold across the new test cases.
- **Backwards-compat:** v0.3 byte-determinism on rectangular fixtures unchanged; circular non-styled fixtures unchanged. The v0.3 NIE for circular `.color_tips` / `.color_tips_by` / `.color_branches_by` is lifted; the per-feature NIE message at `to_svg`-time keeps narrowing to whichever circular features remain unsupported.

### Phase 2 — circular `.scale_bar` + circular `.support_labels`

Closes the last two NIE on circular. Both need a fresh convention call.

- **`.scale_bar` on circular: radial bar.** Pinned: a horizontal line at the canvas's bottom-right (south-east of the tree's bounding circle), label below, length representing N branch-length units in the same `px_per_r` scale the radial layout uses. The "calibration ring" alternative (a unit-radius circle around the tree) was rejected because a circle's *circumference* is angular, not branch-length — it would visually suggest the wrong metric. The radial bar matches the rectangular convention (horizontal ruler) without inventing new geometry. Same `(length, label)` API.
- **`.support_labels` on circular: upright text at the projected internal-node position.** Pinned: same `min_value` filter API as rectangular; rotation_deg = 0 (no rotation, even though tips rotate radially). Justification: support labels are short numerics (e.g., `95`), upright text is more legible at any tree position than rotated text, and crowding at the tree's inner regions is a label-collision problem (deferred to v0.5+ GPU work, per the cadence memory). If a real fixture surfaces where upright support labels overlap their surrounding branches, revisit then.
- **EVIDENT:** new claim `treescape-circular-annotation-determinism` (ci-tier, property-style): same tree + same scale_bar/support_labels config → byte-identical SVG on the circular path. Includes the convention assertions ("scale bar lives in canvas south-east quadrant"; "support labels rotation_deg == 0"). One claim covers both annotations because they share the determinism property and the test fixture set.
- **Backwards-compat:** rectangular `.scale_bar` and `.support_labels` byte-bytes unchanged.

### Phase 3 — branch-stroke width by metadata + terminal-branch coloring

The v0.3 styling story is "color." Phase 3 adds **width** to the same metadata-driven pipeline, plus lifts v0.3's "internal-branches-only" rule so terminals participate in the styling.

- **`.width_branches_by(column, wmin=, wmax=, vmin=, vmax=)`** — numeric-only. Branch stroke-width scales linearly between `wmin` and `wmax` (defaults: 1.0, 4.0 px) over the column's observed `[vmin, vmax]` (defaults: column min/max). For internal branches: subtree mean (same convention as `.color_branches_by` continuous). For terminal branches: the tip's own value. Missing values keep `SceneOptions.stroke_width`. No discrete-column variant in v0.4 — discrete-by-width is unusual and adds the same monophyly-warn scaffold for marginal value; deferred unless a real fixture argues otherwise.
- **Terminal-branch coloring.** v0.3's `.color_branches_by` excluded terminal branches by `if tree.is_tip(node_id): continue`. Phase 3 lifts that. For a terminal branch, the "subtree" is the tip itself — discrete monophyly is trivially satisfied (one tip, one value, no warning) and continuous mean equals the tip's value. The user-visible effect is that terminal branches get the same color as their tip when both `color_tips_by` and `color_branches_by` are applied to the same column — which is what users expect from ggtree-style figures.
- **EVIDENT:**
  - New claim `treescape-branch-width-by-numeric-determinism` (ci-tier, property-style): same column + same `(wmin, wmax, vmin, vmax)` → byte-identical SVG; subtree-mean / tip-value rule asserted explicitly on a fixture with both monophyletic and paraphyletic clades.
  - `treescape-color-branches-by-monophyly`'s claim text is amended to cover terminal branches; the existing test fixture exercises both internal-paraphyletic and terminal cases.
- **Backwards-compat note:** the v0.3 byte-determinism on `tests/fixtures/golden/<fixture>_styled.svg` will **regenerate** on this phase, because terminal-branch coloring changes pixels under existing `.color_branches_by` calls. Track the golden regen explicitly in CHANGELOG (v0.4 is a minor — golden bytes can change). Users who pin against v0.3 SVG bytes need to re-render.

## Explicitly NOT in v0.4

These are real items, but bundling them dilutes the ship. Pushed to v0.5+:

- **PDF export.** Same scene graph, new emitter. Standalone enough to ship as v0.4.x or v0.5 Phase 1.
- **Nexus and PhyloXML parsers.** Each is ~1 phase; defer.
- **Node shape styling.** Would add a new `Marker(x, y, kind, size, fill, stroke)` scene type — net-new geometry vs Phase 3's "stroke-width along existing primitives." v0.5.
- **`treescape-cli` / `treeplot` console.** Surface design needs its own pass.
- **fontdue: kerning + non-Latin shaping.** Wait for a real fixture.
- **GPU label collision avoidance.** Only matters at >10k tips. v0.5+ when a real-world fixture pushes against the CPU baseline.
- **Force-directed unrooted layout.** v0.5+.
- **Columnar-FFI variant for metadata-driven coloring at >50k tips × dense metadata.** v0.5+ if a use case shows up.
- **Circular `.scale_bar` calibration-ring alternative.** Rejected up-front in Phase 2; not a deferred decision.
- **Discrete `.width_branches_by`.** Deferred unless a real fixture argues for it.

## Cadence (same as v0.1, v0.2, v0.3)

For each phase:

1. Lock convention decisions in `docs/conventions.md` **before** any code.
2. Pin EVIDENT claim in `evident.yaml` **before** the test exists.
3. Implement the Python reference (`treescape-reference`).
4. Port to Rust (`treescape-core`) and hold to the Python reference within `1e-9` (or per-claim tolerance).
5. Wire through `treescape-connector` (PyO3) and `TreePlot` grammar.
6. External review at end of phase. Address findings before the next phase.
7. Commit + push per phase milestone.

Per the saved feedback memory: recurring v0.1/v0.2/v0.3 review findings are claim overstatement, undeclared test deps, silent tolerance bumps, and "the test asserts a property the claim doesn't actually make." Watch for those. Round-1 v0.2 caught two P1s (silent no-op on circular options, sweep_total ignored); round-1 v0.3 wasn't run for credit reasons — v0.4 should run review per phase as the cadence prescribes.

## Open questions for the user

1. **Phase 2 circular `.scale_bar` placement.** Pinned in the plan as bottom-right radial bar. Confirm or override.
2. **Phase 2 circular `.support_labels` rotation.** Pinned as upright (`rotation_deg = 0`). Confirm or override (alternative: tangential, matching tip-label convention).
3. **Phase 3 width range defaults.** Pinned as `wmin=1.0, wmax=4.0` px. Confirm or pick different defaults.
4. **Phase 3 terminal-branch coloring rollout.** Pinned as automatic (lifts the v0.3 internal-only restriction; v0.3 goldens regenerate). Alternative: behind a flag like `include_terminal=True` so v0.3 byte-determinism holds. Recommend automatic — terminal coloring is what users expect from `.color_branches_by` and the byte-determinism claim covers fixed inputs, not pinned-across-versions output.

## Success criteria

v0.4 ships when:

- All three phases landed on main (one commit per phase).
- 18 EVIDENT claims green (16 from v0.3 + 2 new: `treescape-circular-annotation-determinism`, `treescape-branch-width-by-numeric-determinism`). Phases 1 and 3 partially extend existing claims (`color-tips-by-discrete-roundtrip`, `color-branches-by-monophyly`, `color-by-continuous-determinism`) rather than adding new ones.
- **Backwards-compat preserved** on rectangular non-`color_branches_by` fixtures: `treescape-svg-determinism` byte-identical for v0.3 fixtures that don't use `color_branches_by`. Rectangular `.color_branches_by` goldens regenerate per Phase 3 (terminal-branch coloring is now active there too); CHANGELOG calls this out as the v0.4 minor's only golden regen.
- External review of all three phases closed (or explicitly waived per phase).
- CI green on `main` (rectangular + circular ci-tier) and on the v0.4.0 tag (release-tier ggtree, both rectangular and circular).
- CHANGELOG updated; tag `v0.4.0` pushed.
- Gallery extended: `assets/gallery/` adds at least three new files showing circular metadata coloring, circular annotation, and branch-width-by-metadata.

## Why this trio over alternatives

Considered alternative: **format coverage** (PDF + Nexus + PhyloXML). The v0.3 plan rejected this exact combination; same critique still applies — the three don't compose in one minor.

Considered alternative: **big trees** (label collision avoidance + force-directed unrooted + columnar FFI). Genuinely interesting, but until a real >10k-tip fixture lands the perf claims are unanchored. v0.4 would be designing speculative invariants. Wait for a fixture.

Considered alternative: **CLI + Jupyter rich display + minor polish.** Productivity surface, no oracle gotchas. Rejected because (a) CLI design needs its own pass and shouldn't be bundled with feature work, (b) Jupyter rich display is small enough to do as a v0.4.x point release.

The chosen trio composes around one thread: **metadata-driven styling.** Phase 1 makes circular reach feature parity for the v0.3 styling vocabulary. Phase 2 closes the last two NIE on circular. Phase 3 adds width to the styling vocabulary and rounds out v0.3's internal-only branch coloring. After v0.4, "I want to publish this figure" should not hit a `NotImplementedError` for any combination of layout + metadata-driven attribute that v0.3+v0.4 covers.
