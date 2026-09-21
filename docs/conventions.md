# Layout conventions

This document records the coordinate conventions treescape uses for tree layout, and the points where each external oracle (ete3, Biopython.Phylo, ggtree) matches or differs.

This is the canonical place for **convention-gap analysis**. When an EVIDENT layout claim disagrees with an oracle, the gap is documented here before any tolerance is loosened.

## treescape conventions (v0.1, rectangular layout only)

The Python reference at `packages/treescape-reference/src/treescape_reference/layout.py` is the canonical convention owner. The Rust port in `treescape-core/src/layout/rectangular.rs` is held to match within `1e-9`.

### x — cumulative branch length

- Root has `x = 0`.
- Every other node has `x = parent.x + node.branch_length`.
- Negative branch lengths produce negative offsets (legal Newick, rare in practice).

### y for tips

- Tips at integer positions `0, 1, …, N-1` in **pre-order** traversal of leaves.
- The topmost tip in pre-order has `y = 0`. In SVG screen coordinates this places it at the top of the canvas.

### y for internal nodes

- `y = arithmetic mean of immediate children's y`.
- For binary trees this matches the "midpoint of first and last child" convention used by Biopython exactly.
- For multifurcating internal nodes the two conventions can differ; the first divergent fixture lands in v0.2.

### Ladderization tie-break

- Children sorted by **subtree size** (number of descendant tips). Stable sort.
- Ties (subtrees of equal size): preserve original child order.
- This is what `treescape-core::ladderize::ladderize(&mut tree, ascending=true)` and the Python reference's `ladderize(tree, ascending=True)` both implement.

### Tip-label width (v0.2+)

v0.1 shipped a 0.6-em monospace approximation: `width = N_chars * font_size * 0.6`. That is wrong for proportional fonts (DejaVu Sans, the bundled face). v0.2 replaces it with real glyph metrics:

- **Font:** the bundled `treescape-render/src/fonts/DejaVuSans.ttf` (compile-time embedded; no system fallback). Both Rust and Python read the same file.
- **Metric:** sum of HMTX **advance widths** for each glyph, scaled to `font_size`. The Python reference reads HMTX directly via `fontTools.ttLib`. The Rust core reads it via `fontdue`'s `metrics()` API. Both should agree to floating-point precision; the EVIDENT claim allows 0.5 px slack to accommodate fontdue's subpixel rounding.
- **No shaping:** v0.2 is Latin-only. No kerning, no ligatures, no contextual substitution, no BiDi. Tip names that need shaping (CJK, Arabic, Devanagari) are out of v0.2 scope; document and revisit when a real fixture surfaces.
- **Default font size:** 12 px. Configurable via `SceneOptions.font_size`.
- **Default measurer:** the fontdue-backed measurer is the default in the connector. The legacy 0.6-em path remains accessible via `SceneOptions.avg_glyph_width` for testing/comparison; passing it overrides the measurer.

This convention shift bumps the canvas width on every fixture (label area widens to fit real glyph widths). Existing SVG goldens were regenerated when this convention landed; the byte-determinism claim still holds, just over different bytes.

## treescape conventions (v0.2, circular layout)

The Python reference at `packages/treescape-reference/src/treescape_reference/layout.py::circular_layout` is the canonical convention owner. The Rust port in `treescape-core/src/layout/circular.rs` is held to match within `1e-9`.

The circular layout is a polar transform of the rectangular layout. Each node has a `(r, θ)` pair; the SVG renderer projects to Cartesian via `(cx + r·cos(θ), cy − r·sin(θ))` (the y-flip is because SVG's y-axis grows downward and we want θ=π/2 to mean "up").

### r — radius (cumulative branch length)

- Identical rule to rectangular's x: root has `r = 0`; every other node has `r = parent.r + node.branch_length`.
- Negative branch lengths are legal Newick but produce an unintuitive "inside-the-root" radius; documented and not specially handled.

### θ — tip angles

- Tips at angles `θ_i = start_angle − (i / N) · sweep_total` for `i = 0, 1, …, N-1` in **pre-order traversal of leaves** (same order rectangular uses for y). The minus sign encodes the clockwise sweep direction (see *Sweep direction* below).
- **`start_angle` default:** `π/2` (90°, 12 o'clock). The first tip in pre-order points straight up. Most published phylogenies orient this way.
- **`sweep_total` default:** `2π` (full circle). Configurable for fan layouts (e.g. `π` produces a half-fan from 12 o'clock, sweeping clockwise back through east).
- **Fan layouts (exposed in v0.7):** `options(start_angle=…, sweep_total=…)` in Python and `options!(p; start_angle, sweep_total)` in Julia, in radians. `start_angle` must be in `[−2π, 2π]` and `sweep_total` in `(0, 2π]`; other values raise at the call. Tips keep the full-circle spacing `sweep_total / N` above, so the last tip sits one gap short of `start_angle − sweep_total` (a half fan, `sweep_total = π`, ends at `π/2 − π·(N−1)/N`). The external circular oracles (ete3, ggtree) are compared at the defaults only; fans are covered by Rust↔reference layout parity, the Python↔Julia byte parity cases and the determinism goldens, not by an external oracle.
- **Sweep direction:** **clockwise** as `i` increases. So with default `start_angle = π/2` and `sweep_total = 2π`, tip 0 is at 12 o'clock and tip `N-1` is just before 12 o'clock again, having swept right (east), down (south), left (west), and back around.

  Note: this is *clockwise* on a clock face but *negative-θ* in math convention. We track it by writing `θ_i = start_angle − (i / N) · sweep_total` internally — the minus sign encodes the direction. Choosing clockwise matches the natural "reading direction" for left-to-right languages: tip 0 at top, tip 1 to its right, and so on around the circle.

### θ — internal nodes

- `θ = arithmetic mean of immediate children's θ`, computed in the **arc-aware sense**: if children's angles wrap (e.g. one at `0.1` rad and one at `2π − 0.1`), the mean is taken on the shorter arc, not the linear average. v0.2 trees with `sweep_total = 2π` can have a root whose children straddle the wrap point; the wrap-aware mean is essential there.

  Implementation: convert each child's θ to `(cos(θ), sin(θ))`, sum the vectors left to right in child order (a plain fold in both implementations, not Python's compensated `sum()`), then `atan2(sum_y, sum_x)`. The mean is undefined when the sum is the origin: the children are spread evenly. That can happen at any node whose tip arc spans more than π, for example a star root, the two opposite children of `two_tip`, or the inner node `(b,(c,d,e),f)` of `(a,(b,(c,d,e),f));`, whose children sit exactly 120° apart. **If the sum's norm is below `1e-9`, the node takes the midpoint of its own tip arc: `start_angle − ((i_first + i_last) / 2 / N) · sweep_total`**, where `i_first` and `i_last` are the pre-order indices of its first and last descendant tip (a node's tips are contiguous). The midpoint lies inside the node's arc, so its radial line and arc stay on the side of its descendants. Sums that are not exactly zero stay far above the threshold (about `1e-5` even at a million tips). *(v0.6: before this rule the angle was rounding noise, and it differed between Rust and the reference; found by the node-level comparison on the random corpus.)*

### Cartesian projection (SVG)

- Canvas is square: `2 · (max_r · px_per_r + padding + max_label_width)` per side.
- Center `(cx, cy)` at canvas midpoint.
- Project: `x_svg = cx + r · cos(θ);  y_svg = cy − r · sin(θ)`.
- Branches: each parent→child edge becomes a **radial line segment** from `(parent.r, child.θ)` to `(child.r, child.θ)`, plus a **circular arc** at `r = parent.r` spanning the children's θ-range. The arc is drawn as an SVG `<path>` with an `A` (elliptical-arc) command.
- Tip labels: positioned at `(r_max + label_offset, θ_tip)` with `text-anchor` chosen so the label reads outward — `start` for tips on the right half, `end` for the left, with rotation transform `rotate(deg, x, y)` to keep text radial.

This is a clean isomorphism with rectangular: `(r, θ) ↔ (x_rect, y_rect)` via `r = x_rect, θ = start_angle − (y_rect / max_y_plus_one) · sweep_total`. The "rectangular and circular layouts are the same data under a polar transform" property is the basis for the `treescape-circular-self-consistent-with-rectangular` invariant claim.

## treescape conventions (v0.3, metadata join)

The Python reference at `packages/treescape-reference/src/treescape_reference/metadata.py::join_metadata` is the canonical convention owner. There is no Rust port for v0.3 — metadata storage and lookup live entirely on the Python side. (See *Storage scope* below for why.)

### Frame type

- **Polars only.** `TreePlot.join_metadata(df, on=...)` accepts `polars.DataFrame`. pandas users convert via `pl.from_pandas(df)`. No `__dataframe__` interchange path; no pandas dual-test path. One supported frame type, one error surface.
- The decision was deliberate. Dual-support and an interchange-via-`__dataframe__` compromise were considered and rejected to keep maintenance burden flat. Reconsider in a v0.x point release if user-reach demands it.

### Join semantics

- The `on=` argument names the column of the user's frame whose values match tree tip names. Required (no default).
- Every tip in the tree has **at most one** row in the joined frame. Tips with no matching row carry `None` for every metadata column. This is "left-outer join from the tree's tip set onto the frame," with the tree as the authoritative tip universe.
- **Validation, all loud:**
  - **Extra rows** (a row whose `on=` value is not a tip in the tree) → `ValueError` listing the offending count and the first 5 unmatched names. Loud because it almost always means the user typoed a tip name or joined the wrong frame; silently dropping is the "metadata didn't apply" failure mode that's hardest to debug.
  - **Duplicate rows** (same `on=` value appearing more than once in the frame) → `ValueError` listing the duplicated value(s). Loud because the resolution is ambiguous (first wins? last wins? error?) and the user should pick.
  - **Empty frame** is legal — every tip ends up with all-None metadata. No warning.

### Storage scope (Python-side, no FFI)

- The joined frame is held on the `TreePlot` instance. Access through the internal `_metadata_for(tip_name) -> dict | None` helper, which returns the row as a plain Python `dict` (column dtypes preserved as Python scalars; `None` if the tip has no row).
- **No metadata FFI to Rust in v0.3.** Phase 2's metadata-driven coloring resolves to `{tip_name: color}` dicts on the Python side and reuses the existing v0.2 `color_tips` / `color_branches_styled_svg` PyO3 paths. The Rust `treescape-core` crate is unchanged by Phase 1.
- **Trade-off:** practical-N for metadata-driven plots is capped at Python dict overhead, not the Rust SoA core's actual capacity. Fine for v0.3's expected scale (≤10k tips × ≤10 columns); a user with 50k+ tips × dense metadata would feel this. Revisit in v0.4 with a columnar-FFI variant if the use case shows up.

### Chained joins

- `.join_metadata(df1, on="tip").join_metadata(df2, on="tip")` adds columns from `df2` to whatever was already joined from `df1`.
- **Column-name collisions raise** `ValueError`. Silent overwrite is the "which frame won?" failure mode that's hardest to debug after the fact. The user resolves by renaming columns in the inbound frame.
- The two frames may use the same or different `on=` columns; both are independently validated against the tree's tip set per the rules above.

### Immutability

- The joined frame stored on `TreePlot` is treated as immutable for the lifetime of the plot. The user mutating their original `df` after `join_metadata` does **not** affect the plot's metadata state. Polars's COW semantics make this cheap (no deep copy required); we just hold the reference and don't expose mutation paths.

### Discrete tip coloring by metadata

- `TreePlot.color_tips_by(column, palette=...)` is a Python-side resolver over joined metadata. It produces the same per-tip color mapping as an explicit `TreePlot.color_tips({...})` call, then reuses the existing v0.2 styled SVG path.
- The column is treated as discrete/categorical. Missing metadata values (`None` from an unmatched tip row) are not colored and keep the default tip-label color.
- If `palette` is provided, it must cover every observed non-None value in tree tip order; missing palette entries raise `ValueError`.
- If `palette` is omitted, values are assigned the Tableau-10 qualitative palette in first-occurrence order over the tree's tip order. More than 10 observed values raise `ValueError`; no cycling, because cycling silently makes unrelated categories share color.

### Discrete branch coloring by metadata

- `TreePlot.color_branches_by(column, palette=...)` colors **every** branch — internal **and** terminal — under the same monophyly rule. The branch is identified by its child node id; the parent→child segment (horizontal in rectangular, radial in circular) receives the color, while the sibling connector (rectangular vertical spine, circular arc) stays at the default stroke color.
- A branch is colored iff every descendant tip under that child node has the same non-None value for `column`. For terminal branches the descendant set is the single tip itself, so the rule is trivially satisfied whenever the tip has a value — terminal-branch color matches its tip's color when both `.color_tips_by` and `.color_branches_by` run on the same column.
- Mixed values, or partial-data clades (some descendants have a value, others are missing), leave the branch at the default color and emit `TreescapeStyleWarning`.
- **All-missing subtrees default silently — no warning.** A branch whose descendants all carry no metadata for the given column is treated as "no data," not "miscoloring." This matches the continuous-color path's silent default on no-data subtrees. (v0.4 review-round-1 refinement; before, terminal branches whose tip was absent from the joined frame would warn for every such tip.)
- Palette rules match `color_tips_by`: user palettes must cover observed non-None values; omitted palettes use Tableau-10 in first occurrence order over tree tips.
- *(Historical, v0.3.0 only):* terminal branches were excluded from the monophyly rule and stayed at the default stroke. v0.4 Phase 3 lifted that restriction; SVG bytes for fixtures that exercise `.color_branches_by` change at the v0.3.0 → v0.4.0 boundary.

### Branch width by metadata + terminal-branch coloring (v0.4 Phase 3)

v0.3 styling shipped color along the metadata-driven pipeline; Phase 3 adds **width** to the same vocabulary, plus lifts v0.3's "internal branches only" rule so terminals participate.

**`.width_branches_by(column, wmin=1.0, wmax=4.0, vmin=None, vmax=None)`** — numeric-only.

- **API and dispatch.** Numeric only; no discrete-by-width variant. The column's observed values must all be `int`/`float` (excluding `bool`); otherwise the method raises `ValueError`. No auto-detection magic — width-by-discrete is rare and the `palette`/`cmap` symmetry the color path uses doesn't translate cleanly to width.
- **Range.** `(wmin, wmax)` defaults to `(1.0, 4.0)` px. The lower bound matches `SceneOptions.stroke_width`'s default so a "minimum" width branch reads visually identical to an unstyled branch; the upper bound is set so emphasis is visible without overwhelming the layout. User can override.
- **Value range.** `(vmin, vmax)` defaults to the column's observed min/max across the tree's tip universe — same convention `color_branches_by` uses, so width and color stay coherent when applied to the same column. Values outside `[vmin, vmax]` are clamped to the endpoints, not extrapolated.
- **Per-branch rule (matches `.color_branches_by` continuous):**
  - **Internal branch:** width = linear-interp(`mean(descendant tips' non-missing values for column)`, in `[vmin, vmax]`, to `[wmin, wmax]`). Subtree mean.
  - **Terminal branch:** width = linear-interp(tip's own value, …). Subtree of one.
  - **No observed values in subtree:** keep `SceneOptions.stroke_width` (default). No warning — same convention as `color_branches_by` continuous, where "no data" is not a paraphyletic miscoloring.
- **Degenerate range** (`vmin == vmax`, or all values equal): every observed value maps to `t = 0.5` → width = `(wmin + wmax) / 2`. Deterministic, no divide-by-zero.
- **Layout coverage.** Both rectangular (parent→child horizontal segment) and circular (radial parent→child Line). The sibling spine — rectangular's vertical connector and circular's arc — keeps `SceneOptions.stroke_width` regardless of width-by-metadata, mirroring the v0.4 Phase 1 color convention ("only the parent→child segment carries the metadata-driven attribute; sibling connectors stay neutral").

**Terminal-branch coloring (v0.4 Phase 3 lift on `.color_branches_by`).**

- v0.3 / v0.4 Phase 1 explicitly excluded terminal branches from `.color_branches_by` (every preorder loop carried `if tree.is_tip(node_id): continue`). Phase 3 lifts that exclusion: terminals participate in monophyly (trivially: one tip, one value, no warning) and in continuous mean (the tip's own value through `cmap`).
- **Visible effect.** When a user calls both `.color_tips_by("col")` and `.color_branches_by("col")` on the same column, the terminal branch and its tip carry the same color — what users expect from ggtree-style figures, what v0.3 quietly didn't deliver.
- **Backwards-compat note.** Bytes change for any existing render that uses `.color_branches_by` without also pinning terminal-branch styling. Test goldens in `tests/fixtures/golden/` are unaffected because none of them route through `color_branches_by` (the styling-determinism `STYLE_SPECS` use highlights + tip_colors only). The `assets/gallery/` SVGs that do use `color_branches_by` (06, 08) regenerate when `scripts/regen_assets.py` runs; the gallery is documentation, not pinned bytes.

**EVIDENT (v0.4 Phase 3):**
- **New claim** `treescape-branch-width-by-numeric-determinism` (ci-tier, property-style): same column + same `(wmin, wmax, vmin, vmax)` → byte-identical SVG; subtree-mean rule on internal branches; tip-value rule on terminals; default `stroke_width` for no-data subtrees.
- **Amended claim** `treescape-color-branches-by-monophyly`: claim text now covers internal AND terminal branches under the same monophyly + warn semantics.

### Circular `.scale_bar` + `.support_labels` (v0.4 Phase 2)

Lifts the v0.3+v0.4-Phase-1 `NotImplementedError` for `TreePlot.scale_bar` and `TreePlot.support_labels` on `.layout("circular")`. After v0.4 Phase 2 lands, the circular path has feature parity with rectangular for every styling primitive v0.3+v0.4 covers.

**`.scale_bar` on circular: bottom-right radial bar.** A horizontal line + end ticks + centered label, identical scene primitives to the rectangular scale bar — only the position differs.

- **Position locked.** The bar sits in the canvas's bottom-right corner, in the unused space outside the tree's bounding circle (the square canvas inscribes a circle of radius `radius_px + label_offset + max_label_px`; the four corners are reliably empty).
  - Right endpoint: `bar_x2 = canvas_width − padding`.
  - Bar y: `bar_y = canvas_height − padding − font_size · 1.2` (one label-height above the bottom padding boundary, leaving room for the label below).
  - Left endpoint: `bar_x1 = bar_x2 − length · px_per_r`. The bar extends *leftward* from the right edge — opposite of the rectangular convention's "extends right from the left edge" — so the user can ask for any reasonable length without it running off-canvas.
- **Length scaling.** `length` (in branch-length units) maps to pixels via `px_per_r`, the same scale the radial axis uses. Tip and bar share the same scale by construction.
- **Ticks + label.** Same as rectangular: end ticks (vertical tick marks at `bar_x1` and `bar_x2`, height `max(font_size · 0.35, 3.0)` px) plus a centered label below the bar at `(bar_x1 + bar_x2) / 2, bar_y + font_size · 1.2`.
- **Label inside the canvas (v0.7; both layouts, the rectangular bar included).** A label wider than the bar used to be clipped: centred on a bar that touches the padding, half of it fell outside the canvas (the v0.6 gallery showed "5 substitutions/site"). The label stays centred on the bar but moves inward just enough to stay inside the padding. With label width `w` (measured like tip labels): rectangular, `x = max((bar_x1 + bar_x2) / 2, padding + w / 2)`, and the canvas is at least `x + w / 2 + padding` wide; circular, `x = min((bar_x1 + bar_x2) / 2, canvas_width − padding − w / 2)`, and when the bar or the label is wider than `canvas_width − 2 · padding` the canvas widens to the right (to `2 · padding + max(length · px_per_r, w)`; the tree stays centred at `half`, so the canvas is no longer square). A label no wider than its bar (and, for circular plots, a bar that fits the canvas) is not moved, so those outputs are byte-identical to v0.6. Clade highlights keep the tree's own width when the canvas widens for a scale bar. On a small circular tree a long label can overlap the tree and its tip labels.
- **No calibration-ring alternative.** A circle's circumference is angular, not branch-length — using a unit-radius ring as the "scale" would visually suggest the wrong metric. Rejected up-front; not a deferred decision.

**`.support_labels` on circular: upright text at the projected internal-node position.** Same `min_value` filter API as rectangular.

- **Position locked.** For each internal node with a non-empty name (and value ≥ `min_value` if specified), emit one `Text` at `(cx + r · px_per_r · cos(θ), cy − r · px_per_r · sin(θ))`. No offset from the node's projected position — the label sits at the junction.
- **`rotation_deg = 0`.** Upright, not tangential to the radial axis (tip labels rotate; support labels do not). Justification: support labels are short numerics (`95`, `0.97`) and upright text is more legible at any tree position; rotated text loses readability when angled past 90° from horizontal. Crowding at the tree's inner regions is a label-collision problem, deferred to v0.5+ GPU work per the cadence memory.
- **`anchor = TextAnchor.Middle`.** Centers the label on the projected position so it reads as "this is the value of this node" rather than offset to one side.
- **`min_value` filter.** Same parsing rule as rectangular: internal-node names that don't parse as `f64` are skipped when `min_value` is set; values below the threshold are skipped.

**EVIDENT (v0.4 Phase 2):** new claim `treescape-circular-annotation-determinism` (ci-tier, property-style). Same tree + same `(scale_bar, support_labels)` config → byte-identical SVG on the circular path. Includes convention assertions: scale-bar `bar_x2 == canvas_width − padding`; support-label `rotation_deg == 0` and `anchor == Middle`. One claim covers both annotations because they share the determinism property and the test fixture set.

### Circular tip + branch coloring (v0.4 Phase 1)

Lifts the v0.3 `NotImplementedError` for `TreePlot.color_tips`, `TreePlot.color_tips_by`, and `TreePlot.color_branches_by` on `.layout("circular")`. Mirrors v0.3 Phase 2 rectangular semantics where the meaning is the same; one circular-specific convention is documented below.

- **Tip color** is per-`Text` `fill`, identical to the rectangular convention. No new scene primitive. The fontdue-measured rotation/anchor of circular tip labels is unchanged — only the fill color changes per tip.
- **Branch color: which scene primitive carries it.** The v0.3 rectangular convention is "the horizontal parent→child segment receives the color while the vertical connector spine stays at the default stroke color." The circular analogue:
  - **The radial parent→child `Line` (from `(parent.r, child.θ)` to `(child.r, child.θ)`) receives the color.** That line is the parent-to-child branch.
  - **The arc spine (at `r = parent.r`, spanning the children's θ-range) stays at the default stroke color.** The spine connects siblings, not parent-to-child; it is not "a branch" in the metadata-coloring sense.
  - This means a colored circular branch is visually a single radial line segment from the parent's radius outward to the child's. Sibling spines under a paraphyletic-by-`column` parent stay default-stroke even when the children's branches are differently colored — same visual idiom as rectangular's vertical-spine-stays-default convention, just rotated into polar.
- **Monophyly logic** (discrete `color_branches_by`) follows the same rule as rectangular: every descendant tip shares the same non-missing value → palette color; mixed or partial-data → default + `TreescapeStyleWarning`; all-missing → silent default. v0.4 Phase 3 lifted v0.3's "internal branches only" rule, so terminal branches (1-tip subtrees) participate on circular too — see *Discrete branch coloring by metadata* above for the canonical specification.
- **Continuous (subtree-mean viridis)** follows the same rule as rectangular: every branch (internal **and** terminal as of v0.4 Phase 3) is colored by `cmap(mean(descendant tips' non-missing values for column))`, with `(vmin, vmax)` defaulting to the column's observed min/max so tip and branch coloring share a coherent scale by construction. For a terminal branch the mean equals the tip's own value, so the terminal stroke matches its tip when both `color_tips_by("col")` and `color_branches_by("col")` run on the same column. Subtrees with no observed values keep the default radial-line stroke silently. See *Continuous coloring by metadata* below for the canonical specification.
- **Z-order** (v0.3 Phase 3 convention preserved): `AnnularSector` items emit before `Line` / `Arc` / `Text`, so highlights render behind the colored radial branches. Branch coloring on top of a highlight still reads correctly (highlight tints the background, branch stroke remains visible).
- **EVIDENT (v0.4 Phase 1):** `treescape-color-tips-by-discrete-roundtrip`, `treescape-color-branches-by-monophyly`, and `treescape-color-by-continuous-determinism` are each **extended** (not replaced) to cover circular layouts. New circular fixtures land alongside the existing rectangular ones; Rust↔Python ref byte parity continues to hold.

### Circular clade highlighting (annular sectors, v0.3 Phase 3)

Closes the v0.2 `NotImplementedError` for `TreePlot.highlight_clade(...)` with `.layout("circular")`. Other circular styling features (`.color_tips`, `.color_tips_by`, `.color_branches_by`, `.scale_bar`, `.support_labels`) remain `NotImplementedError` for now — they're natural follow-ups but not in v0.3 Phase 3 scope.

- **New scene type:** `AnnularSector(cx, cy, r_inner, r_outer, theta_min, theta_max, fill)` in both Python reference (`scene.py`) and Rust core (`layout/scene.rs`). Coordinates are in **pixels** (post-projection), matching `Rect` — the scene-graph layer never carries layout-coordinate values.
- **Geometry per highlight:**
  - `r_inner = mrca_r * px_per_x` where `mrca_r` is the layout radius of `MRCA(tip_names)`. The sector's inner edge sits at the MRCA, mirroring v0.2's rectangular convention where the highlight starts at the MRCA's branch point.
  - `r_outer = max_r * px_per_x + label_offset + max_label_px` — the same outer extent the canvas reserves for tip labels. Every highlight extends to the same outer radius, the polar analogue of v0.2's "rectangle extends to canvas right edge."
  - `theta_min`, `theta_max` = min and max layout tip angles among `clade_tips(MRCA)`. Internal-node angles do not bound the sector — only tip angles do, matching the rectangular convention where row span is the clade's tip rows.
- **MRCA == root → raise.** A clade whose MRCA is the root covers every tip; the highlight would cover the whole canvas (visually meaningless, blocks every branch and label). `TreePlot.highlight_clade(...)` paired with `.layout("circular")` raises `ValueError` at `to_svg`-time when this happens. Wrap-split paths are dead code under v0.3's `start_angle = π/2`, `sweep = 2π` convention (see *θ — tip angles* and Phase 3 plan); a fan layout (`sweep_total < 2π`) reopens this question.
- **Z-order:** `AnnularSector` items are emitted before `Line`, `Arc`, and `Text`, so highlights render behind branches and labels. Same z-order as `Rect` in the rectangular path.
- **SVG emit (path data):** `M r_inner·cosθ_min, ... L r_outer·cosθ_min, ... A r_outer r_outer 0 large 0 r_outer·cosθ_max, ... L r_inner·cosθ_max, ... A r_inner r_inner 0 large 1 r_inner·cosθ_min, ... Z`. The outer arc uses SVG `sweep_flag = 0` (increasing-θ direction = CCW visually under our SVG y-flip — same convention used by the existing arc spines); the inner arc returns with `sweep_flag = 1`. `large_arc = 1` iff `theta_max − theta_min > π`. Float formatting (`{:.4}` trim trailing zeros) matches the existing arc renderer.
- **EVIDENT claim:** `treescape-styling-determinism` is **extended**, not replaced. Byte-determinism property carries over unchanged. Additional property: an annular sector's `[theta_min, theta_max]` equals the min/max layout tip angles in the clade. The radial bounds use the layout's own `[r_mrca, r_max + label_zone]` convention; rectangular↔circular shape equivalence under the polar transform is **not** claimed — each layout is byte-deterministic in its own conventions, no cross-shape parity.

### Continuous coloring by metadata

- `TreePlot.color_tips_by(column, cmap=...)` and `TreePlot.color_branches_by(column, cmap=...)` map a numeric metadata column through a colormap. Dispatch is auto-detected from the column's observed dtype: all-numeric (excluding `bool`) → continuous; otherwise → discrete. Pass `cmap=` (continuous) or `palette=` (discrete) to force the path; passing both raises `ValueError`.
- **Default colormap: viridis.** treescape ships its own pinned 11-keystop viridis LUT (since v0.5 in `treescape-core/src/style.rs::VIRIDIS_LUT`; oracle copy in `treescape_reference.style.VIRIDIS_LUT`), with linear RGB interpolation between stops. This is *not* byte-identical to matplotlib's full 256-stop viridis; visual fidelity is approximate, byte-determinism is exact. The LUT endpoints are `#440154` at `t=0` and `#fde725` at `t=1`. A LUT change is a treescape-version-level break and regenerates golden SVG bytes — track it explicitly in CHANGELOG.
- **Range:** `vmin` and `vmax` default to the column's observed min/max across the tree's tip universe. Pin them explicitly to keep colors stable across plots that share a scale (e.g., subplots). Values outside `[vmin, vmax]` are clamped to the colormap endpoints, not extrapolated.
- **Degenerate range:** when `vmin == vmax` (or the column has all-equal observed values), `t = 0.5` (colormap midpoint) for every value. Avoids divide-by-zero; deterministic; one colormap step rather than half. Documented choice; revisit only if a real fixture argues otherwise.
- **Branch coloring (numeric):** every branch (internal **and** terminal as of v0.4 Phase 3) is colored by the **mean** of its descendant tips' non-missing values for `column`, mapped through `cmap`. For a terminal branch the descendant set is the single tip itself, so the "mean" equals the tip's own value — terminal-branch color matches its tip's color when both `color_tips_by("col")` and `color_branches_by("col")` run on the same column. A branch with no observed values keeps the default color silently — no warning, since "no data" is not a paraphyletic miscoloring (contrast with the discrete monophyly claim, which warns on mixed/partial-data). Tip and branch coloring share the same `(vmin, vmax)` by default, so coloring on the same column produces a coherent scale.
- **Callable cmaps** are accepted (`cmap=callable`) and called as `cmap(t: float) -> "#rrggbb"`. The callable must be deterministic and locale-independent for the EVIDENT byte-determinism claim to hold.

### Styling resolution in Rust (v0.5 Phase 1)

v0.3–v0.4 resolved metadata-driven styling in `plot.py`. v0.5 Phase 1 moves the resolution rules into `treescape-core::style` so every host language (Python now, Julia in Phase 2) shares one implementation. **Behavior-preserving on Python ≥ 3.12:** every v0.4 golden and gallery SVG is byte-identical before and after. On Python 3.11 subtree means change to the 3.12 result (see *Subtree-mean summation* below). The Python oracle is `treescape_reference.style`, adapted from the v0.4 `plot.py` before the Rust port existed.

**Moves to Rust:** Tableau-10 palette and default-palette assignment (>10 values raises), the pinned viridis LUT, `value_range`, `normalize`, the discrete monophyly rule, subtree means for continuous color and width, and width scaling.

**Stays in the host:**

- **Dataframe handling and join validation.** Join keys are host-native values (a polars `Int64` key column is legitimate and must fail with the v0.3 "not a tree tip" error, not a type error at the FFI). Each host implements the v0.3 join semantics above; the shared error semantics are pinned by the existing `treescape-metadata-join-roundtrip` fixtures.
- **Numeric-vs-discrete detection.** Python excludes `bool`; Julia's `Bool <: Integer` needs its own explicit exclusion (Phase 2).
- **Color *input* parsing** (`"#rrggbb"`, tuples). Hosts have idiomatic color types; Rust never parses user color strings. Palette entries are parsed by the host, lazily, exactly where v0.4 parsed them.
- **Callable `cmap`.** Rust returns per-node `t ∈ [0, 1]`; the built-in `"viridis"` maps through Rust, a callable maps in the host.
- **`TreescapeStyleWarning`.** Rust returns the non-monophyletic node ids in preorder; the host formats the unchanged v0.4 message and emits it before the atomic assignment (v0.4 review round 3).

**Input domains.** Palette sizes are ints ≥ 0; discrete codes are ints in `[0, 2**32)`; node ids are ints in `[0, n_nodes)`; every column's length equals the tree's tip count. Out-of-domain input raises `ValueError` (`IndexError` for node ids) with the same message from the reference and the connector.

**Boundary shape.** Columns cross as vectors aligned to `tip_order()` (preorder tips, unnamed tips included): numeric as `Option<f64>`, discrete as `Option<u32>` codes. Codes are indices into the first-occurrence list of distinct values over tip order — the same order the default palette assigns in. Descendant-tip sets skip unnamed tips, as v0.4's `_descendant_tips` did.

**Numeric semantics pinned for byte parity** (each one is a place a naive port silently diverges):

- **Subtree-mean summation** is Neumaier-compensated, exactly as CPython ≥ 3.12's builtin `sum()` over floats: running sum `s`, compensation `c`; per term `t = s + x`, `c += (s − t) + x` if `|s| ≥ |x|` else `(x − t) + s`, `s = t`; at the end `s += c` only when `c` is nonzero and finite. Terms are added in `_descendant_tips` order (left-to-right preorder). *Why pinned:* v0.4 used builtin `sum()`, whose float algorithm changed in Python 3.12 (`sum([1e16, 1.0, -1e16])` is `0.0` on 3.11, `1.0` on 3.12). treescape supports Python ≥ 3.11, so v0.4 subtree-mean colors and widths could differ by interpreter version; goldens were generated on 3.12. Pinning the 3.12 algorithm in Rust keeps the goldens and makes 3.11 output match them.
- **Viridis channel rounding is round-half-to-even** (Python `round()`), i.e. Rust `f64::round_ties_even`, not `f64::round`.
- **Observed min/max follow Python `min()`/`max()`**: start from the first observed value, replace on strict `<` (min) / `>` (max). With NaN present the result is order-dependent — preserved rather than "fixed", since fixing it would be a behavior change.
- **NaN through viridis is an error**, with Python's message: `cannot convert float NaN to integer` (what `int(round(nan))` raised in v0.4). A callable `cmap` receives the NaN `t` unchanged, as before.

## Julia binding (v0.5 Phase 2)

`Treescape.jl` (`packages/Treescape.jl/`) drives the same Rust core through `treescape-jl-connector`, a C-ABI cdylib — the rustims `imsjl_connector` pattern. Its contract is **byte-identical SVG to Python for the same inputs** (claim `treescape-julia-python-svg-parity`); everything below exists to make that true or to keep the Julia process alive.

### C ABI

- Symbols are prefixed `ts_`. `ts_abi_version()` returns `1`; `Treescape.jl` refuses to load a library with a different version rather than calling into a mismatched ABI.
- **Status codes:** every fallible call returns `int32`: `0` ok, `1` invalid argument (null pointer, invalid UTF-8, out-of-range node id, column-length mismatch), `2` Newick parse error, `3` styling-resolution error (e.g. NaN through viridis, palette exhausted), `4` render error (e.g. highlight MRCA is the root). A non-zero status comes with an owned UTF-8 message through the `char **err` out-parameter (null, or a pointer that fails the checks below, discards it). A null options pointer selects the defaults; a non-null one that fails the checks is an error. The message text is the same string Python's exception carries.
- **Ownership:** handles (`TsTree`, `TsStyle`) and returned strings are owned by the caller and released with `ts_tree_free` / `ts_style_free` / `ts_string_free`; each accepts null. Output destinations are validated before a string is allocated, so a rejected call leaks nothing. Julia attaches `ts_tree_free` as a finalizer (with the function pointer resolved at construction, so the finalizer does no lookup) and passes the owning `Tree` object — not its raw pointer — to every `ccall`, which roots it for the call's duration. All symbols are resolved once, under a lock, when the library loads.
- **No panics across the boundary.** The workspace release profile sets `panic = "abort"` (not overridable per package), so a Rust panic would kill the Julia process. The connector denies `clippy::unwrap_used`, `expect_used`, `panic` and `indexing_slicing`, validates every pointer, string and id before touching the core, and returns a status instead. The only panic site on core/render paths is the `expect` on parsing the compile-time-embedded DejaVu Sans, which cannot fail for a correctly built library.
- **Pointer checks:** every pointer argument is checked for null, alignment for its element type, and a total size within `isize::MAX` bytes before a slice is formed, so a wrong length or misaligned buffer becomes status `1` rather than undefined behavior. What cannot be checked — a dangling or already-freed handle, a buffer shorter than its stated length — is the caller's contract; `Treescape.jl` never exposes raw handles or buffers.
- **Input and output limits:** Newick input over 16 MiB is rejected with status `1` before parsing. Parsing costs about 30× the input on typical trees and up to about 160× in the worst case (every byte opens a node). The parser's large buffers grow fallibly, so running out of memory there is status `2` ("input too large to parse in available memory"), in Python a `ValueError`, rather than an abort. Small per-node allocations are still infallible; the cap keeps them far from exhaustion. The SVG emitter — shared with Python — refuses to write non-finite numbers (status `4` / `RuntimeError`) and replaces characters XML 1.0 forbids (C0 controls other than tab/LF/CR, U+FFFE, U+FFFF) with U+FFFD in text content.
- **Columns** cross as `(values*, present*, len)` pairs: `double` or `uint32` values plus a `uint8` presence mask (0 = missing), aligned to tip order — the Phase 1 boundary shape. Node ids are 0-based on the C side.

### Host semantics mirrored from `plot.py`

`Treescape.jl` re-implements only the host-side concerns listed under *Styling resolution in Rust*; each mirrors `plot.py` so the resulting render calls are identical:

- **Source heuristic:** same as `_load_tree` — inline Newick if the string contains a newline, ends with `;` or starts with `(` (after stripping), otherwise a file path; an existing path that does not start with `(` wins.
- **`options!`**: `px_per_x` also sets the circular `px_per_r`; `px_per_y` is rectangular-only; unspecified values keep their current setting.
- **Colors:** `"#rrggbb"` / `"#rrggbbaa"` (leading `#`s stripped) or 3-/4-tuples of reals truncated toward zero, as Python's `int()`. Python additionally accepts oddities such as sign or whitespace inside a hex pair (`int("+f", 16)`); Julia rejects them — an error-path-only divergence.
- **`highlight_clade!` alpha:** applied iff the color is opaque and `alpha != 1.0`; `round(clamp(alpha * 255, 0, 255))` in both hosts — clamping first so huge finite values (where `alpha * 255` overflows to `inf`) clamp to 255 instead of raising. Both `round`s are ties-to-even. Non-finite alpha raises (`ValueError` / `ArgumentError`).
- **`scale_bar` length / label:** the length must be finite and `> 0` in both hosts (NaN and `inf` raise at the call, not at render time). A non-string label is formatted as Python's `str()` would: floats as `pyfloat` (`1e-05`), `True`/`False` for booleans.
- **`cmap`:** `"viridis"` / `:viridis` / `nothing`, or any callable accepting a float (a `Function` or a callable struct), as Python's `callable()`.
- **Numeric vs discrete:** all observed values are `Real` and none is `Bool` → continuous. Missing is `missing` or `nothing`.
- **Discrete values** are deduplicated in first-occurrence tip order, and palette keys matched, with Python's category equality: `a === b || a == b`. So `-0.0` and `0.0` are one category, as are `1` and `1.0`, and a NaN matches only itself. (Julia's `isequal` would split `-0.0` from `0.0`; review round 1 finding.)
- **Default scale-bar label** is the length formatted like Python's `str(float(x))` (`0.05`, `1.0`, `1e-05`, `1e+16`), not Julia's `string(x)` (`1.0e-5`).
- **Warnings:** non-monophyletic branches log `@warn` with `_group = :treescape_style` and the same message text as `TreescapeStyleWarning`, emitted before the atomic assignment.
- **Metadata:** any Tables.jl source; `on` is a column name (`Symbol` or `String`). Join validation (missing `on` column, duplicate keys, non-tip keys, column collisions) follows the v0.3 semantics with the same messages.

### Library discovery

`ENV["TREESCAPE_JL_LIB"]` → Preferences.jl `libpath` (`Treescape.set_library!(path)`) → the development build `<repo>/target/release/libtreescape_jl_connector.{so,dylib}` next to a source checkout → an error that says how to build it (`cargo build -p treescape-jl-connector --release`). No JLL in v0.5.

## EVIDENT manifest (v0.6 Phase 1)

`evident.yaml` follows the upstream EVIDENT schema (`evident/workflow/SCHEMA.md`) and must pass both upstream gates: `evident/workflow/validate_manifest.py` and `typed-trust`. The prose fields (`claim`, `assumptions`, `failure_modes`) are for readers. The structured fields below are the data, and `tests/oracle/test_manifest.py` keeps them honest.

**Subsystems:** `parser` (Newick), `layout` (rectangular and circular coordinates, ladderize), `text-metrics` (label widths), `render` (SVG emission), `style` (styling resolution and metadata-driven styling), `metadata` (tip joins), `julia-binding` (Python↔Julia parity), `ffi` (C-ABI robustness).

**Oracles.** Each is a vocabulary term with a pinned version in every claim that names it:

| Oracle | What it is | Version pinned as |
|---|---|---|
| `Biopython` | Bio.Phylo, external | installed version (CI and the release image pin the same one) |
| `ete3` | ete3, external | installed version |
| `ggtree` | R/ggtree (Bioconductor), external, release image only | `ggtree <v> (Bioconductor <v>, R <v>)` |
| `treescape-reference` | the readable Python reference in this repository | the treescape version |
| `golden-snapshots` | committed SVGs (`tests/fixtures/golden/`, `assets/`) | the treescape version |
| `self-consistency` | round-trip, repeated-render and explicit-equivalence checks within treescape | the treescape version |
| `treescape-python` | the Python package as Julia's parity partner | the treescape version |
| `hypothesis` | property-based random-tree generator | installed version |
| `julia-subprocess` | the Julia process-survival harness | the Julia versions CI runs |

The in-repository oracles are not independent of treescape. They are listed so that a reader can see which claims rest *only* on self-consistency. An oracle names only what the claim's own `evidence.command` runs: Miri, for instance, runs the FFI unit tests in a separate CI job and is described in the FFI claim's prose, not listed as its oracle. Besides oracles, a claim pins the runtime when its result depends on it (`python` for the Neumaier-sum claim, `julia` for the Julia parity claim). `tests/oracle/test_manifest.py` requires every vocabulary oracle to be classified as a Python package (pin = installed version), in-repository (pin = workspace version), or checked elsewhere (ggtree in the release image).

**Tolerance metrics:** `absolute_error` (base vocabulary; the unit is stated in `prose`), `mismatch_count` (project vocabulary: the number of compared items that differ, such as bytes, tokens, colors or statuses; always `== 0`), and `pass_rate` (base vocabulary: the fraction of cases or generated examples that satisfy a property; always `== 1.0`). Each entry's `op` and `value` are the comparison the runner actually asserts. `prose` keeps the original wording.

**Inputs.** `inputs.n` counts the items the claim is asserted over: fixture files or cases for fixture corpora, generated examples for `random-sample`, and test cases for runner-built `synthetic` inputs. Every claim whose class includes `fixture` must name a corpus from `tests/fixtures/corpora.toml` and carry its `corpus_sha`.

**Corpora.** A claim's `inputs.corpus` names an entry in `tests/fixtures/corpora.toml`, which lists the fixture files. `inputs.corpus_sha` is `sha256:` of the text `path\nsha256(file)\n` for each listed file in sorted path order (`scripts/corpus_sha.py`). A claim whose inputs are built inside its runner uses `class: synthetic` with the runner as `corpus`. `release`-tier claims over more than one input must carry `corpus_sha` (schema rule). Every `corpus_sha` is recomputed by the manifest test, so a changed fixture cannot silently keep an old hash.

**Pinned versions:** every measurement claim pins `treescape` (the workspace version in `Cargo.toml`) and every oracle it names. The manifest test checks the `treescape` pin against `Cargo.toml`, and the Python oracle pins against the installed packages. The ggtree pin is checked inside the release image.

## Layout oracle corpus and node-level comparison (v0.6 Phase 2)

### Random tree corpus

`scripts/gen_random_trees.py` writes `tests/fixtures/trees/random/*.nwk`. The files are checked in and hashed through the `layout-v2` corpus, so every oracle, including ggtree in the release image, reads the same bytes, and the script only regenerates them. Rules:

- **Seed** `20260921`, one `random.Random` stream for the whole corpus, trees generated in a fixed order.
- **Sizes** 3, 4, 5, 7, 10, 16, 25, 40, 64, 100, 150, 200 tips.
- **Shapes**, one tree per size and shape:
  - `yule`: split a uniformly chosen tip;
  - `pda`: attach the new tip to a uniformly chosen edge, including above the root;
  - `ladder`: caterpillar;
  - `polytomy`: `yule`, then each internal edge collapsed with probability 0.3, giving multifurcations;
  - `zeros`: `yule` with each branch length set to 0 with probability 0.2.
- **Branch lengths**: exponential with mean 0.1, rounded to 6 decimals, written with Python `repr` of the rounded float, so the Newick round-trip is exact. The root has no branch length.
- **Names**: `t001`, `t002`, … (unique, unquoted).

### Node identity across implementations

A node is identified by its **clade**: the set of tip names below it (a tip's clade is its own name). The corpus has unique tip names, so clades identify nodes independently of each tool's internal ids and child order.

### What each oracle is compared on

Both treescape implementations (`treescape-reference` and the Rust core via `treescape_connector`) are compared with each oracle, on every node the oracle defines.

| Oracle | Rectangular | Circular |
|---|---|---|
| Rust ↔ reference | every node, `(x, y)` | every node, `(r, θ)` |
| ete3 | every node `x` (`get_distance`); tip `y` (leaf index in `iter_leaves`). ete3 has no internal-y rule to compare. | every node `r`; tip `θ` from ete3's leaf order through treescape's angle formula. This checks leaf *order* and distances only, not the angle rule. |
| Biopython | every node `x`; tip `y` (after `−1`); internal `y` on nodes whose whole subtree is binary. At a multifurcation Biopython uses the midpoint of the first and last child, treescape the mean of all children (see the gap table), and because an internal y is the mean of its children's, the difference propagates to every ancestor. | — (no circular layout) |
| ggtree | every node `x` and `y` (after `+1`; ggtree also uses the mean of the children) | every node `r`; tip `θ` (transform in the disagreement log). Internal `θ` is not compared: ggtree takes the linear mean, treescape the wrap-aware vector mean. |

## Trees from distance matrices (v0.6 Phase 3)

`treescape_reference.tree_build` is the convention owner; `treescape-core::tree_build` is held to it (exact topology, branch lengths within `1e-12`). Both follow the steps below in the same floating-point order, including every tie, so they build the same tree.

### Input

- `D`: an `n × n` matrix, `n ≥ 2`, and `n` labels. Rejected, with the offending row and column named: non-square, non-finite, a non-zero diagonal, a negative entry, or asymmetry beyond `|D[i][j] − D[j][i]| ≤ 1e-9 · max(1, |D[i][j]|)`. Only the upper triangle (`i < j`) is read.
- Labels: unique, non-empty strings. They become the tip names.
- `n = 2`: a root with the two tips, each at `D[0][1] / 2`, for both methods.

### Common bookkeeping

An **active list** holds the current clusters, starting with the taxa in input order. Each step picks a pair of positions `p < q` in the list, joins them into a new node with children `[L[p], L[q]]` in that order, removes both, and **appends** the new node at the end. All sums are left-to-right folds in list order. **Ties:** the first pair in `(p, q)` order, `p` ascending, then `q` ascending (a strict `<` scan).

### Neighbor joining

Saitou and Nei (1987), with the Studier and Keppler criterion (the "canonical" NJ). MATLAB's `seqneighjoin(..., 'equivar')` is documented as the same method, but no MATLAB is available to test it, so treescape makes no MATLAB-equivalence claim:

- With `r` active clusters: `R(k) = Σ_m d(k, m)`, and `Q(p, q) = (r − 2)·d(p, q) − R(p) − R(q)`. Join the pair that minimizes `Q`.
- Branch lengths: `δ_p = d(p,q)/2 + (R(p) − R(q)) / (2(r − 2))` and `δ_q = d(p,q) − δ_p`.
- New distances: `d(u, k) = (d(p,k) + d(q,k) − d(p,q)) / 2`.
- When three clusters `a, b, c` remain (list order), they become the three children of the **root**, with `δ_a = (d_ab + d_ac − d_bc)/2`, `δ_b = (d_ab + d_bc − d_ac)/2` and `δ_c = (d_ac + d_bc − d_ab)/2`. NJ trees are unrooted. treescape draws them from this last join, a trifurcating root, and does not midpoint-root implicitly.
- **Negative branch lengths are kept**, as ape does. scikit-bio clamps them to 0 by default, so its oracle runs with `neg_as_zero=False`.

### UPGMA

Average linkage (Sokal and Michener, 1958):

- Join the pair minimizing `d(p, q)`. The new node's height is `d(p,q)/2`, and each child's branch length is `height(u) − height(child)`; tips have height 0.
- `d(u, k) = (|p|·d(p,k) + |q|·d(q,k)) / (|p| + |q|)`, weighted by cluster sizes. This is what makes it UPGMA rather than WPGMA.
- The root is the last join. The tree is ultrametric.

### From a SciPy linkage matrix

`TreePlot.from_linkage(Z, labels)`: row `i` of `Z` joins clusters `Z[i,0]` and `Z[i,1]` (ids `≥ n` are earlier rows) at distance `Z[i,2]`. That node's height is `Z[i,2] / 2`, so that the path between two tips equals their merge distance, which is the UPGMA convention above. SciPy's own `dendrogram` draws at `Z[i,2]` and is therefore twice as tall. Children are in the order `Z[i,0], Z[i,1]`.

### Comparing trees

- **NJ** trees are compared **unrooted**. Each edge is identified by its split: the side that does not contain the first label, or the tip for a pendant edge. A root with two children is merged into a single edge (the sum of the two lengths), so the rooting each tool chooses does not matter. Topology must match exactly, and each edge length within the tolerance.
- **UPGMA** trees are compared **rooted**: each node is identified by its clade, with its height. Clades must match exactly, and each height within the tolerance.

### Oracle behaviour (why each oracle is used, or not)

| Tool | NJ | UPGMA |
|---|---|---|
| scikit-bio `nj` | independent implementation; clamps negative lengths unless `neg_as_zero=False` | `upgma` wraps SciPy's `linkage`, so it is not independent and not used |
| Biopython `DistanceTreeConstructor` | independent, pure Python; ties: first minimum in its own index order, which differs from ours because the merged node takes the lower index | **`upgma` is WPGMA**: it updates `d(u,k) = (d(p,k) + d(q,k)) / 2` without cluster sizes. Not a UPGMA oracle; excluded, and logged below |
| SciPy `linkage(method="average")` | — | independent (C, nearest-neighbour chain) |
| ape `nj` / phangorn `upgma` (R, release tier) | independent | independent |

**Ties** decide the tree when several pairs share the minimum. The oracles break them differently, so oracle agreement is claimed on tie-free matrices only. Tie behaviour is pinned by the Rust↔reference claim and by dedicated tie fixtures.

## Distribution (v0.7 Phase 1)

### Python wheels

- `treescape_connector` is built against CPython's **stable ABI** (`abi3`, Python ≥ 3.11). That gives one wheel per platform:
  - Linux: manylinux2014 (glibc ≥ 2.17), x86-64 and aarch64;
  - macOS: arm64 and x86-64, deployment target 11.0;
  - Windows: x86-64.
- An sdist is published as well, for other platforms (it needs a Rust toolchain).
- `treescape` and `treescape-reference` are pure-Python wheels.
- Every wheel is checked with `twine check`, and is tested **installed**, in a clean virtual environment on its own platform, before the upload. The connector sdist is also built into a wheel and tested that way, license files included; that is what platforms without a prebuilt wheel get.
- The Windows Julia library links the C runtime statically (`+crt-static`): Julia does not ship the MSVC runtime.
- Upload is to PyPI through trusted publishing from `.github/workflows/release.yml`, on a `v*` tag only, and only after the repository owner approves the `pypi` environment. No API token exists.

### Julia library artifacts

- The C-ABI library `libtreescape_jl_connector` is built for the same five platforms. Linux builds use `cargo zigbuild` against glibc 2.17 (the manylinux2014 baseline), so the library loads on older distributions.
- Each platform's library is packed into a tarball together with `LICENSE` and `LICENSE.DejaVu.txt` (the font is embedded). The tarballs are attached to a GitHub release named `jl-connector-v<version>`.
- `packages/Treescape.jl/Artifacts.toml` binds them, **lazily** and per platform (arch, os, libc), by their git-tree hash and sha256. The file is generated by the release workflow, never edited by hand.
- **Order of a release:**
  1. Bump every version to the release version: the workspace `Cargo.toml`, the three pyprojects, `Project.toml`, the two `__version__` strings, and the `treescape` pins in `evident.yaml`.
  2. On that commit, run `release.yml` manually with stage `julia-libs` and `publish_jl_release` ticked. It builds the libraries, creates the `jl-connector-v<version>` release, and produces `Artifacts.toml` plus `ARTIFACTS_SOURCE` (the commit the libraries were built from). A version's release is never replaced: its tarballs back committed hashes.
  3. Commit both files into `packages/Treescape.jl/`, then run stage `build-and-test`. This is the first real download of the artifacts, on every platform and Julia 1.10 and 1.12.
  4. Tag `v<version>`. The tag run checks that every version equals the tag and that the Rust sources are unchanged since `ARTIFACTS_SOURCE`, then builds, tests and publishes the Python packages.
- **Library discovery order:** `ENV["TREESCAPE_JL_LIB"]`, then the `libpath` preference, then **a development build** at `<repo>/target/release/` next to the package, then **the artifact** for this platform (downloaded on first use). A development build wins over the artifact so that a checkout always runs the code under test. Installed copies have no development build, so they use the artifact. The ABI-version check applies to every source.

## Distances from aligned sequences (v0.7 Phase 2)

`treescape_reference.seq_distance` is the convention owner; `treescape-core::seq_distance` is held to it within `1e-12`.

### Input

- **Aligned sequences only.** Sequences of different lengths are an error that names the first sequence whose length differs from the first sequence's and says to align first (MAFFT, MUSCLE, Clustal Omega). Nothing is aligned implicitly.
- At least 2 sequences. Labels must be unique and non-empty.
- **FASTA:** lines are split on `\n`, and a trailing `\r` is dropped (so `\n` and `\r\n` endings work; a bare `\r` is not a line break). Whitespace means the ASCII characters space, tab, `\r`, `\v` and `\f`, nothing else. A record starts at a line beginning with `>` (after leading whitespace). The label is the header's first whitespace-separated word. Sequence lines are concatenated, with whitespace removed. Lines before the first `>` are an error. A string that starts with `>` (after leading whitespace) is FASTA text; any other string is a path.
- **Check order** (the first failure is reported): at least 2 records; each label non-empty and unique; each sequence ASCII; equal lengths; a known alphabet; each character in the alphabet; a model available for the alphabet; then each pair (a usable column, not saturated).
- **Messages** quote labels, characters and names as Python's `ascii()` does: `repr` with every character outside printable ASCII escaped (`'M\xfcller'`, `'a\x01'`). Both implementations produce the same bytes without Unicode tables.
- **Characters:** sequences must be ASCII. A non-ASCII character is an error that names the sequence and the column, checked before uppercasing and before the length and alphabet checks, because uppercasing some of them (`ß` → `SS`) would change the length. Letters are case-insensitive. For **nucleotides**, `U` is read as `T`. For proteins, `U` (selenocysteine) is not definite.

### Alphabets

- **Nucleotide.** Definite characters: `A C G T` (and `U`). Gap: `-`, `.`. Ambiguity codes (not definite): `N R Y S W K M B D H V`.
- **Protein.** Definite characters: the 20 amino acids `A C D E F G H I K L M N P Q R S T V W Y`. Gap: `-`, `.`. Not definite: `X B Z J U O *`.
- `alphabet="auto"` (the default) chooses nucleotide if every non-gap character of every sequence is a nucleotide code (`ACGTUNRYSWKMBDHV`), otherwise protein. Any other character is an error that names the sequence and the position (1-based column).
- **Auto-detection pitfall:** a short protein made only of letters that are also nucleotide codes (for example `MKWVTGAYRSDHNC`) is detected as nucleotide, and most of its letters then count as ambiguity codes. When auto-detection chooses nucleotide but more than half of all non-gap characters are nucleotide ambiguity codes, both hosts warn (Python `TreescapeSequenceWarning`, Julia `@warn` with group `:treescape_sequence`) and suggest `alphabet="protein"`. The result itself is unchanged.

### Pairwise deletion

For each pair, only columns where **both** sequences have a definite character count. With `L` usable columns and `d` differences, `p = d / L`. `L = 0` is an error that names the pair. This is ape's `dist.dna(..., pairwise.deletion = TRUE)` and scikit-bio's behaviour.

### Models

| Model | Alphabet | Distance | Undefined (error) when | Reference |
|---|---|---|---|---|
| `p` | both | `p` | never | proportion of differing sites |
| `jc69` | both | `−((k−1)/k) · ln(1 − (k/(k−1))·p)`, with `k = 4` (nucleotide) or `k = 20` (protein) | `p ≥ (k−1)/k` | Jukes and Cantor (1969); the `k`-state form as in Nei and Kumar (2000) |
| `k2p` | nucleotide | `−(1/2) · ln(1 − 2P − Q) − (1/4) · ln(1 − 2Q)`, with `P` = transitions / `L` and `Q` = transversions / `L` | `1 − 2P − Q ≤ 0` or `1 − 2Q ≤ 0` | Kimura (1980) |
| `poisson` | protein | `−ln(1 − p)` | `p ≥ 1` | Poisson correction (Nei and Kumar 2000) |

- Transitions are `A↔G` and `C↔T`; every other nucleotide difference is a transversion.
- The logarithm is the natural log, computed as `ln(x)` (not `log1p`), which matches the scikit-bio and ape formulas.
- An undefined value (saturation) is an **error** that names the pair and the observed `p`, or `P` and `Q` for K2P. It never becomes `NaN` or `∞` in the matrix, because a tree cannot be built from one.
- **Saturation is decided on exact integer counts**, not on rounded proportions. With `L` usable columns, `d` differences, `s` transitions and `v` transversions: JC69 is undefined when `k·d ≥ (k−1)·L`; K2P when `L − 2s − v ≤ 0` or `L − 2v ≤ 0`; Poisson when `d ≥ L`. K2P's logarithm arguments are computed as `(L − 2s − v)/L` and `(L − 2v)/L`. (With proportions, `1 − 2P − Q` at the exact boundary rounds to about `5.5e−17` and passes as a finite distance; scikit-bio does exactly that. See the disagreement log.)
- Identical sequences (no differing usable column) have distance `+0.0`, returned before any correction. Evaluated literally, every correction gives `−c·ln(1) = −0.0` there.

### Output

A symmetric matrix with a zero diagonal, labels in input order. Each pair is computed once, as `(i, j)` with `i < j`, then mirrored, so the matrix is exactly symmetric and can go straight to `TreePlot.from_distances`.

### Limits

The Julia boundary rejects FASTA text (or, for records, the sum of the sequence lengths) over 64 MiB and more than 10,000 sequences with status `1`, before building anything; the FASTA headers are counted first. 10,000 is also the tree builders' limit. The matrix is `n²` doubles, so 10,000 sequences need 800 MB for the matrix alone (twice that while Python converts it to rows), and the `n²/2` pairs each scan the whole alignment. The Python host applies no limit of its own.

## Orientation (v0.7 Phase 3)

`orientation` names the direction the tree grows, from the root towards the tips: `"right"` (the default; root on the left), `"down"` (root at the top, a dendrogram), `"left"` and `"up"`. It applies to the rectangular layout only. Asking for any orientation except `"right"` with the circular layout is an error when the plot is rendered, not ignored; the circular layout's direction is set by `start_angle` and `sweep_total`.

### An exact transform of the `"right"` scene

The layout is unchanged. The `"right"` scene is built exactly as before (so every existing output is unchanged), then every item is transformed. With the `"right"` canvas `W × H`:

| Orientation | Point `(x, y)` → | Canvas | Rectangle `(x, y, w, h)` → | Text anchor | Text rotation |
|---|---|---|---|---|---|
| `right` | `(x, y)` | `W × H` | unchanged | unchanged | unchanged |
| `left` | `(W − x, y)` | `W × H` | `(W − x − w, y, w, h)` | start ↔ end | unchanged |
| `down` | `(y, x)` | `H × W` | `(y, x, h, w)` | start ↔ end | `θ − 90°` |
| `up` | `(y, W − x)` | `H × W` | `(y, W − x − w, h, w)` | unchanged | `θ − 90°` |

`left` is a reflection across the vertical axis, `down` a reflection across the diagonal (a transpose), and `up` a rotation by 90° counter-clockwise. The differences are computed as written (`W − x`, in double precision) in both implementations.

- **Tip order:** the first tip stays first: at the top for `right` and `left`, on the left for `down` and `up`.
- **Tip labels** are placed away from the root. For `down` and `up` they are rotated −90° (they read bottom to top, as in R's `plot(hclust)` and SciPy's `dendrogram`), hanging below the tips for `down` and standing above them for `up`. The anchor swap keeps each label on the far side of its tip, and the text stays centred on its tip's row.
- **Everything else follows the same transform:** clade highlights, the scale bar and its label, and support labels. The scale bar runs along the depth axis: horizontal for `right` and `left`, vertical for `down` and `up`.
- A transpose of text would mirror glyphs, so text is never transposed: only its anchor point moves, and the rotation and anchor columns above keep it readable.



| Convention | treescape | ete3 | Biopython.Phylo | ggtree |
|---|---|---|---|---|
| tip y origin | `0` (top) | `0` (top) | `1` (top) — see below | `1` — see below |
| tip y direction | top→bottom increasing | top→bottom increasing | top→bottom increasing | bottom→top increasing in `p$data$y` (ggplot2 y-axis grows up); numerically still file-order with `ladderize=FALSE` |
| internal y rule | mean of immediate children | mean of immediate children | midpoint of first & last child | mean of immediate children |
| x rule | cumulative branch length from root | cumulative branch length from root | `tree.depths()` (cumulative) | `p$data$x` (cumulative) |
| default ladderize | off | off | n/a | **on** — `ggtree()` ladderizes by default; oracle disables via `ladderize=FALSE` |
| ladderize tie-break | stable, preserve original | stable, preserve original | n/a | inherits ape `ladderize` order |

### Biopython y offset

Biopython's `_get_y_positions` returns `1, 2, …, N` (1-indexed, top-to-bottom). treescape uses `0, 1, …, N-1`.

**Comparison rule:** `our_y == biopython_y - 1`. The oracle test applies this offset before comparing, with the offset documented in the test source.

### ggtree y offset

ggtree's `p$data$y` for tips is `1, 2, …, N`, in file-order *when* `ladderize = FALSE` is passed to `ggtree()`. treescape uses `0, 1, …, N-1`.

**Comparison rule:** `our_y + 1 == ggtree_y`. The oracle test applies this offset before comparing, with the offset documented in the test source (`tests/oracle/test_layout_vs_ggtree.py`).

### ggtree default ladderize

`ggtree()` defaults to `ladderize = TRUE`, which reorders children by clade size before assigning y-coordinates. `treescape.rectangular_layout` does *not* ladderize implicitly — that is a separate, explicit `ladderize()` step. To make the oracle a like-for-like comparison, `workflow/scripts/oracle_ggtree.R` invokes `ggtree(tree, ladderize = FALSE)`.

This was discovered while running claim `treescape-layout-vs-ggtree` for the first time (2026-04-28). With `ladderize = TRUE`, ggtree's tip y for `((((a,b),c),d),e)` is `a=4, b=5, c=3, d=2, e=1`, which is not a simple flip or offset of our `a=0..e=4`. With `ladderize = FALSE` it becomes `a=1..e=5`, a clean `+1` offset.

### ggtree scale drift

ggtree's `p$data$x` is in unit-branch-length space and matches our convention exactly for trees with all positive branch lengths. For negative branches, ggplot's internal scaling can produce drift up to `1e-5`; the oracle test tolerance of `1e-4` accommodates this.

## Disagreement log

When an oracle disagrees with treescape on a fixture and the gap is real (not a tolerance issue), it is logged here:

| Date | Fixture | Oracle | Gap | Resolution |
|---|---|---|---|---|
| 2026-04-28 | `small/two_tip.nwk`, `small/balanced_4.nwk`, `small/unbalanced_5.nwk`, `edge/trifurcation_root.nwk` | ggtree 4.0.5 | Tip y values diverged from treescape/ete3/Biopython on first run of claim `treescape-layout-vs-ggtree`. Two causes: ggtree's default `ladderize = TRUE` reorders children by clade size; ggtree's tip y is 1-based. | Pass `ladderize = FALSE` in `workflow/scripts/oracle_ggtree.R` (matches treescape's "no implicit ladderize" convention); apply `+1` offset in the oracle test (matches the Biopython oracle's pattern). No tolerance change. |
| 2026-04-28 | `small/two_tip.nwk`, `small/balanced_4.nwk`, `small/unbalanced_5.nwk`, `edge/trifurcation_root.nwk` | ggtree 4.0.5 (circular) | Tip θ diverged on first run of claim `treescape-circular-layout-vs-ggtree`. Cause: ggtree places tip *i* (1-based) at angle ``i·2π/N`` sweeping **CCW** with the LAST tip at 3 o'clock (0); treescape places tip *i* (0-based) at ``π/2 − i·2π/N`` sweeping **CW** with the FIRST tip at 12 o'clock (π/2). The two formulas combine into per-tip ``θ_ggtree = 2π/N + π/2 − θ_ours`` (mod 2π). Internal-node angles also diverge (ggtree linear mean, treescape wrap-aware vector mean) but the oracle test compares tips only. | Apply the per-tip θ transform in `tests/oracle/test_circular_layout_vs_ggtree.py`. Internal-node convention covered by Rust↔reference parity instead. No tolerance change. |
| 2026-09-21 | `random/polytomy_*.nwk` (121 multifurcating nodes in the corpus; 200 nodes whose subtree is not binary) | Biopython 1.88 | Internal y at a node with more than two children: Biopython places it at the midpoint of its first and last child, treescape at the mean of all children. Because an internal y is the mean of its children's, the difference propagates to every ancestor: 136 of the 200 non-binary-subtree nodes differ, by up to 14.8 rows. Known since v0.1 (gap table); first exercised by the v0.6 node-level comparison. | Internal y compared only for nodes whose whole subtree is binary, where both rules agree. The rest is excluded by rule, not by tolerance. No tolerance change. |
| 2026-09-21 | any matrix where cluster sizes differ | Biopython 1.88 (`DistanceTreeConstructor.upgma`) | Biopython's "upgma" updates distances as `(d(p,k) + d(q,k)) / 2`, which is WPGMA. True UPGMA weights by cluster size. The two agree only when every join is between equal-sized clusters. | Biopython is not used as a UPGMA oracle. UPGMA is checked against SciPy (ci) and phangorn (release). No tolerance change. |
| 2026-09-21 | `alignments/protein.fasta` (`p1`/`p3`) | ape 5.8.1 (`dist.aa`, `pairwise.deletion = TRUE`) | For proteins, ape counts a gap opposite a residue as a difference (3/22), while treescape removes the column pair by pair (2/21), as it does for nucleotides and as ape's own `dist.dna` does. ape does remove `X`. | Protein pairs where either sequence has a gap, or one of `B Z J U O *` (whose handling in `dist.aa` is undocumented), are excluded from the ape comparison by rule and listed in the report. Nucleotide comparisons are unaffected. No tolerance change. |
| 2026-09-21 | `alignments/boundary_k2p.fasta` (`a`/`b`: 3 columns, 1 transition, 1 transversion); 23 simulated pairs in `alignments-v1` | scikit-bio 0.7.3 (`k2p`); ape 5.8.1 (`dist.dna`, `K80` and `JC69`) | At the exact K2P boundary `L − 2s − v = 0`, both oracles compute the logarithm's argument from proportions, get a rounding residue of about `5.5e−17` and return a finite distance (about 19–20). treescape decides saturation on the integer counts and raises an error naming the pair. Where the residue is exactly 0 (for example `L − 2v = 0`, or the JC69 boundary in `boundary_jc69.fasta`), the oracles return NaN and agree with treescape. On `alignments-v1` this excludes 23 K2P pairs from each oracle and no JC69 pair. | A pair is excluded only when it is on the boundary by the integer rule **and** the oracle's value is finite; each exclusion is listed in the runner's report. Every other boundary pair is still compared. No tolerance change. |
