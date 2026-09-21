# Distance-matrix fixtures

Hand-written matrices for the tree-building claims (`docs/conventions.md`, "Trees from distance matrices"). Format: tab-separated; the first line is the labels, followed by `n` rows of `n` numbers. The generated `distance-v1` corpus is not stored here; `scripts/gen_distance_matrices.py` derives it from the pinned random trees.

| File | n | What it exercises |
|---|---|---|
| `ties_equidistant_4.tsv` | 4 | every pair tied: the tie rule decides every join (first pair in `(p, q)` order) |
| `ties_textbook_5.tsv` | 5 | the standard NJ teaching example (Saitou and Nei's scheme, as in most textbooks and Wikipedia); its second NJ step has two pairs with equal Q |
| `ties_zero_pairs_6.tsv` | 6 | identical taxa (zero distances), as in the course's human mtDNA matrix with 6 zero pairs; UPGMA ties at 0 and at 0.2 |
