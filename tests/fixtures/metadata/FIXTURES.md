# Metadata fixtures (v0.3)

Companion CSVs for the tree fixtures at `tests/fixtures/trees/`. Used by `treescape-metadata-join-roundtrip` (Phase 1) and Phase 2's coloring claims.

| Path | Tree | Columns | Notes |
|---|---|---|---|
| `small/two_tip.csv` | `trees/small/two_tip.nwk` | `tip`, `clade`, `support` | smallest non-trivial join; `clade` is paraphyletic at root (`x`/`y`) so the only internal branch is the paraphyletic case |
| `small/balanced_4.csv` | `trees/small/balanced_4.nwk` | `tip`, `clade`, `support` | `clade` makes `MRCA(a,b)` and `MRCA(c,d)` monophyletic (`left`/`right`); the root is paraphyletic. Exercises both Phase 2 branch-coloring paths in one fixture |
| `small/unbalanced_5.csv` | `trees/small/unbalanced_5.nwk` | `tip`, `clade`, `support` | `clade` makes `MRCA(a,b)` and `MRCA(a,b,c)` monophyletic by `inner`; deeper MRCAs paraphyletic. Multiple monophyletic clades on a ladder |

## Conventions

- **`tip` column** is the join key — values must match Newick tip names exactly (case-sensitive). The `on=` argument to `TreePlot.join_metadata` defaults to `"tip"` for these fixtures.
- **`clade` column** is the discrete-color test column. Values are short string labels chosen so that at least one MRCA is monophyletic and at least one is paraphyletic per fixture. This is required for Phase 2's `treescape-color-branches-by-monophyly` claim to exercise both code paths from a single fixture.
- **`support` column** is the continuous-color test column. Values in `[0.5, 1.0]` mimicking bootstrap support; specific numbers chosen for readable goldens, not biological meaning.

## Synthetic only (v0.3)

All v0.3 metadata fixtures are synthetic. Real biological metadata (lineage assignments, divergence dates, phenotypic traits) brings citation and license footprint that isn't justified for v0.3's scope. Real fixtures land when a use case demands them.

## Adding a metadata fixture

1. The companion tree fixture must already exist in `tests/fixtures/trees/`.
2. Hand-check that `clade`-style columns produce at least one monophyletic and one paraphyletic clade — otherwise Phase 2's branch-coloring tests will only cover one path from this fixture.
3. Add a row to the table above.
4. Like tree fixtures, never edit a metadata fixture in place — joined SVG goldens may be pinned against the exact values.
