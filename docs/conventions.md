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
