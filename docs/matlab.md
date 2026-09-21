# Coming from MATLAB

If you are porting MATLAB Bioinformatics Toolbox code to Python or Julia, this page maps the usual tree-building steps onto treescape. The Python and Julia code below runs in CI and must reproduce the image on this page byte for byte, like the [examples](examples.md). The MATLAB code follows the MathWorks documentation but is **not** run: there is no MATLAB in CI.

## The steps side by side

| Step | MATLAB | Python | Julia |
|---|---|---|---|
| Read aligned FASTA | `fastaread(file)` | `distances.read_fasta(path)` | read by `distances(path)` |
| Distances | `seqpdist(seqs, 'Method', 'Jukes-Cantor', 'Alphabet', 'NT')` | `distances.from_fasta(path, model="jc69")` | `distances(path; model = :jc69)` |
| Distance models | `'p-distance'`, `'Jukes-Cantor'`, `'Kimura'`; proteins also `'Poisson'` | `"p"`, `"jc69"`, `"k2p"`, `"poisson"` | `:p`, `:jc69`, `:k2p`, `:poisson` |
| Gaps | `'Indels'`: `'score'` (default), `'pairwise-delete'`, `'complete-delete'` | always removed pair by pair, with ambiguity codes | same |
| UPGMA | `seqlinkage(D, 'average', seqs)` | `TreePlot.from_distances(D, labels, method="upgma")` | `TreePlot(D, labels; method = :upgma)` |
| Neighbor joining | `seqneighjoin(D, 'equivar', seqs)` | `method="nj"` | `method = :nj` |
| Sequences to tree in one call | – | `TreePlot.from_sequences(path, model=…, method=…)` | – |
| A linkage matrix | `Z = linkage(…)` (1-based, 3 columns) | `TreePlot.from_linkage(Z, labels)` (SciPy layout) | `from_linkage(Z, labels)` (SciPy layout) |
| Root at the top | `'Orientation', 'top'` | `.orientation("down")` | `orientation!(p, :down)` |
| Root at the bottom / left / right | `'bottom'` / `'left'` / `'right'` | `"up"` / `"right"` / `"left"` | `:up` / `:right` / `:left` |
| Show or save | `plot(tree)`, `view(tree)` | `.save("tree.svg")`, or display in a notebook | `save(p, "tree.svg")`, or display in Pluto/IJulia |
| Newick | `getnewickstr(tree)` | `.to_newick()` | `to_newick(p)` |

Things to know when comparing results:

- **Orientation names differ.** MATLAB's `'Orientation'` names the side the root is on; treescape's `orientation` names the direction the tree grows. MATLAB's `'top'` is treescape's `"down"`.
- **Alphabet.** `seqpdist` assumes amino acids unless told `'Alphabet', 'NT'`; treescape detects nucleotides (`alphabet="auto"`) and warns when that looks doubtful. Pass the alphabet explicitly on both sides when comparing numbers.
- **Gaps.** treescape always removes gaps and ambiguity codes pair by pair, which is `seqpdist`'s `'Indels', 'pairwise-delete'`, not its default. On gap-free alignments, like the one below, the two agree.
- **Labels.** treescape uses the first word of each FASTA header; MATLAB's `fastaread` keeps the whole header line.
- **Linkage matrices.** MATLAB's `linkage` numbers clusters from 1 and has three columns; SciPy's (which treescape reads) from 0, with a fourth column for cluster sizes. Convert with `[Z(:, 1:2) - 1, Z(:, 3), zeros(size(Z, 1), 1)]`. treescape puts each node at half its merge distance (the path between two tips equals their distance), so its trees are half as tall as MATLAB's or SciPy's `dendrogram` of the same matrix.
- **Aligned input only.** Align first (MAFFT, MUSCLE, Clustal Omega, or MATLAB's `multialign`). Sequences of different lengths are an error that says so.
- **Checked against other tools, not MATLAB.** Distances and trees are compared with scikit-bio, SciPy and R's ape and phangorn (see the [claims](claims.md)).

## A worked example

The cytochrome b genes of 11 primates, taken from their RefSeq mitochondrial genomes (the accessions are in the FASTA headers; `scripts/fetch_primates_cytb.py` fetches them again). The alignment is codons 1–379 of each gene. The full proteins differ by one residue at the C-terminus (380 in apes and Old World monkeys, 379 in New World monkeys); up to there the translations line up without gaps (the fetch script checks for internal stop codons, and that the last 40 residues match in register far better than shifted by one codon).

<!-- setup -->
=== "MATLAB"

    ```matlab
    seqs = fastaread('tests/fixtures/sequences/primates_cytb.fasta');
    ```

=== "Python"

    ```python
    from treescape import TreePlot, distances

    FASTA = "tests/fixtures/sequences/primates_cytb.fasta"
    ```

=== "Julia"

    ```julia
    using Treescape

    FASTA = "tests/fixtures/sequences/primates_cytb.fasta"
    ```

Jukes–Cantor distances, UPGMA, and a dendrogram with the root at the top:

<!-- example: 17_dendrogram_from_sequences.svg -->
=== "MATLAB"

    ```matlab
    D = seqpdist(seqs, 'Method', 'Jukes-Cantor', 'Alphabet', 'NT');
    tree = seqlinkage(D, 'average', seqs);
    plot(tree, 'Orientation', 'top');
    ```

=== "Python"

    ```python
    D, labels = distances.from_fasta(FASTA, model="jc69")
    p = (
        TreePlot.from_distances(D, labels, method="upgma")
        .orientation("down")
        .options(padding=16, px_per_x=1500, px_per_y=24, font_size=12)
        .scale_bar(0.02)
    )
    p.save("tree.svg")
    ```

=== "Julia"

    ```julia
    D, labels = distances(FASTA; model = :jc69)
    p = TreePlot(D, labels; method = :upgma)
    orientation!(p, :down)
    options!(p; padding=16, px_per_x=1500, px_per_y=24, font_size=12)
    scale_bar!(p, 0.02)
    save(p, "tree.svg")
    ```

![UPGMA dendrogram of primate cytochrome b](assets/gallery/17_dendrogram_from_sequences.svg)

For neighbor joining, use `method="nj"` (Python) or `method = :nj` (Julia), like `seqneighjoin`. Neighbor joining does not assume a molecular clock, but its tree is unrooted: treescape draws it from its last join, which is not an estimate of the root. Read its branching order as unrooted.
