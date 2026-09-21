# Alignment fixtures

Hand-written FASTA files for the sequence-distance claims (`docs/conventions.md`, "Distances from aligned sequences"). The simulated `alignments-v1` corpus is not stored; `scripts/gen_alignments.py` derives it from the pinned random trees.

| File | What it exercises |
|---|---|
| `gaps_and_ambiguity.fasta` | gaps and `N` removed pair by pair; a header with a description; a sequence split over two lines |
| `rna_lowercase.fasta` | lowercase letters and `U` read as `T` |
| `protein.fasta` | the protein alphabet with a gap and `X`; the protein models (`p`, `jc69` with 20 states, `poisson`) |
| `saturated.fasta` | pairs beyond the JC69 and K2P limits: an error that names the pair, never NaN |
| `unaligned.fasta` | sequences of different lengths: an error that says to align first |
| `no_overlap.fasta` | a pair with no column where both have a definite character: an error that names the pair |
| `iupac_codes.fasta` | every IUPAC ambiguity code and the `.` gap, all removed pair by pair |
| `invalid_character.fasta` | a character outside the alphabet under a label with a quote and a control byte: an error that names both, escaped |
| `protein_u.fasta` | protein `U` (selenocysteine) kept as `U`, not read as `T`, and not counted as definite |
| `boundary_jc69.fasta` | p exactly 3/4: JC69 saturates on the integer boundary |
| `boundary_k2p.fasta` | 2P + Q exactly 1 (one transition, one transversion in three columns): K2P saturates on the integer boundary |
| `doubtful_protein.fasta` | a short protein made only of letters that are also nucleotide codes: `alphabet="auto"` reads it as nucleotides and the hosts warn |
