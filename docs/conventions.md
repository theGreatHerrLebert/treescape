# Layout conventions

This document records the coordinate conventions treescape uses for tree layout, and the points where each external oracle (ete3, Biopython.Phylo, ggtree) matches or differs.

This is the canonical place for **convention-gap analysis**. When an EVIDENT layout claim disagrees with an oracle, the gap is documented here before any tolerance is loosened.

## treescape conventions (v0.1, rectangular layout only)

(To be filled during Phase 2 implementation. The `treescape-reference` Python package is the canonical convention owner — every choice below is implemented there first.)

### Tip y-coordinates

TBD — fill when `treescape_reference.layout.rectangular_layout` is written.

### Internal node x-coordinates

TBD.

### Root x-coordinate

TBD.

### Branch direction conventions

TBD.

## Convention gaps vs external oracles

| Convention | treescape | ete3 | Biopython.Phylo | ggtree |
|---|---|---|---|---|
| tip y-spacing | TBD | TBD | TBD | TBD |
| internal x-placement | TBD | TBD | TBD | TBD |
| root x-position | TBD | TBD | TBD | TBD |
| ladderize tie-break | TBD | TBD | TBD | TBD |

Each row lands during Phase 2 with a code citation for the oracle's relevant source line.

## Disagreement log

When an oracle disagrees with treescape on a fixture and the gap is real (not a tolerance issue), it is logged here:

| Date | Fixture | Oracle | Gap | Resolution |
|---|---|---|---|---|

(Empty in v0.1; populated as oracles run.)
