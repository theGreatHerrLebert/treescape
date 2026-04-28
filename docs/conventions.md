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
- **Sweep direction:** **clockwise** as `i` increases. So with default `start_angle = π/2` and `sweep_total = 2π`, tip 0 is at 12 o'clock and tip `N-1` is just before 12 o'clock again, having swept right (east), down (south), left (west), and back around.

  Note: this is *clockwise* on a clock face but *negative-θ* in math convention. We track it by writing `θ_i = start_angle − (i / N) · sweep_total` internally — the minus sign encodes the direction. Choosing clockwise matches the natural "reading direction" for left-to-right languages: tip 0 at top, tip 1 to its right, and so on around the circle.

### θ — internal nodes

- `θ = arithmetic mean of immediate children's θ`, computed in the **arc-aware sense**: if children's angles wrap (e.g. one at `0.1` rad and one at `2π − 0.1`), the mean is taken on the shorter arc, not the linear average. v0.2 trees with `sweep_total = 2π` can have a root whose children straddle the wrap point; the wrap-aware mean is essential there.

  Implementation: convert each child's θ to `(cos(θ), sin(θ))`, take the vector mean, then `atan2(mean_y, mean_x)`. Ill-defined only if children's angles are diametrically opposed (vector mean is the origin); for monophyletic clades this is impossible because the tip angles span less than 2π by construction.

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

- `TreePlot.color_branches_by(column, palette=...)` colors rectangular internal branches only. The branch is identified by its child internal node id; the horizontal parent→child segment receives the color while the vertical connector spine stays at the default stroke color.
- A branch is colored iff every descendant tip under that child node has the same non-None value for `column`. Mixed values or missing values leave the branch at the default color and emit `TreescapeStyleWarning`.
- Palette rules match `color_tips_by`: user palettes must cover observed non-None values; omitted palettes use Tableau-10 in first occurrence order over tree tips.
- Terminal branches are out of scope for v0.3's monophyly claim. They remain default-colored until a separate terminal-branch styling API lands.

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
- **Default colormap: viridis.** treescape ships its own pinned 11-keystop viridis LUT in `packages/treescape/src/treescape/plot.py::_VIRIDIS_LUT`, with linear RGB interpolation between stops. This is *not* byte-identical to matplotlib's full 256-stop viridis; visual fidelity is approximate, byte-determinism is exact. The LUT endpoints are `#440154` at `t=0` and `#fde725` at `t=1`. A LUT change is a treescape-version-level break and regenerates golden SVG bytes — track it explicitly in CHANGELOG.
- **Range:** `vmin` and `vmax` default to the column's observed min/max across the tree's tip universe. Pin them explicitly to keep colors stable across plots that share a scale (e.g., subplots). Values outside `[vmin, vmax]` are clamped to the colormap endpoints, not extrapolated.
- **Degenerate range:** when `vmin == vmax` (or the column has all-equal observed values), `t = 0.5` (colormap midpoint) for every value. Avoids divide-by-zero; deterministic; one colormap step rather than half. Documented choice; revisit only if a real fixture argues otherwise.
- **Branch coloring (numeric):** each internal branch is colored by the **mean** of its descendant tips' non-missing values for `column`, mapped through `cmap`. A branch with no observed values keeps the default color silently — no warning, since "no data" is not a paraphyletic miscoloring (contrast with the discrete monophyly claim, which warns on mixed/missing). Tip and branch coloring share the same `(vmin, vmax)` by default, so calling both `color_tips_by("col")` and `color_branches_by("col")` on the same column produces a coherent scale.
- **Callable cmaps** are accepted (`cmap=callable`) and called as `cmap(t: float) -> "#rrggbb"`. The callable must be deterministic and locale-independent for the EVIDENT byte-determinism claim to hold.

## Convention gaps vs external oracles

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
