# Tree fixtures

Every fixture used by an EVIDENT claim lives here. Fixtures are versioned with the repo and referenced by relative path from `evident.yaml`. A claim that depends on a fixture not listed here is broken — there is no other place fixtures may live.

| Path | Tips | Source | Notes |
|---|---|---|---|
| `small/two_tip.nwk` | 2 | hand-written | smallest non-trivial tree |
| `small/balanced_4.nwk` | 4 | hand-written | balanced binary, equal branches — easiest oracle target |
| `small/unbalanced_5.nwk` | 5 | hand-written | left-heavy ladder, exercises ladderize |
| `edge/quoted_names.nwk` | 2 | hand-written | single-quoted tip names with spaces |
| `edge/nhx_comments.nwk` | 2 | hand-written | NHX `[&&NHX:...]` annotations |
| `edge/neg_branches.nwk` | 2 | hand-written | negative branch length (legal but unusual) |
| `edge/trifurcation_root.nwk` | 3 | hand-written | unrooted-style 3-way root |

## Adding a fixture

1. Hand-check the topology and branch lengths against the Newick string before committing.
2. Add a row to this table with source and what edge case it exercises.
3. If a claim should consume it, list it in that claim's `evidence.fixtures` in `evident.yaml`.
4. Never edit a fixture in place — claims may have golden artifacts pinned against the exact bytes. Add a new fixture instead.

## Medium and large fixtures

`medium/` and `large/` directories are intentionally empty in v0.1. Real biological fixtures (e.g. NCBI mammals, COVID lineage trees) land in v0.2 alongside metadata-driven styling claims. Each must arrive with a license note.
