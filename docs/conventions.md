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
