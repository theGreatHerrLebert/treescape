# Examples

Every example is shown in Python and Julia. Both produce the **same SVG, byte for byte** — the image under each example. CI runs every code block on this page and compares its output with that image (claim [`treescape-julia-python-svg-parity`](claims.md#treescape-julia-python-svg-parity)), so the examples cannot drift from the code.

All examples use the 11-tip primate tree shipped with the repository and a small metadata table. Run them from the repository root.

## Setup

<!-- setup -->
=== "Python"

    ```python
    import polars as pl
    from treescape import TreePlot

    TREE = "tests/fixtures/trees/medium/primates.nwk"
    GREAT_APES = ["Homo_sapiens", "Pan_troglodytes", "Gorilla_gorilla", "Pongo_abelii"]
    META = pl.DataFrame({
        "tip": ["Homo_sapiens", "Pan_troglodytes", "Gorilla_gorilla", "Pongo_abelii",
                "Hylobates_lar", "Macaca_mulatta", "Papio_anubis", "Cercopithecus_mitis",
                "Chlorocebus_sabaeus", "Callithrix_jacchus", "Saimiri_sciureus"],
        "clade": ["great_apes"] * 4 + ["lesser_apes"] + ["old_world_monkeys"] * 4
                 + ["new_world_monkeys"] * 2,
        "support": [0.99, 0.97, 0.95, 0.91, 0.88, 0.93, 0.92, 0.85, 0.83, 0.78, 0.75],
    })
    ```

=== "Julia"

    ```julia
    using Treescape

    TREE = "tests/fixtures/trees/medium/primates.nwk"
    GREAT_APES = ["Homo_sapiens", "Pan_troglodytes", "Gorilla_gorilla", "Pongo_abelii"]
    # Any Tables.jl source works: a DataFrame, a CSV.File, or a NamedTuple of vectors.
    META = (
        tip = ["Homo_sapiens", "Pan_troglodytes", "Gorilla_gorilla", "Pongo_abelii",
               "Hylobates_lar", "Macaca_mulatta", "Papio_anubis", "Cercopithecus_mitis",
               "Chlorocebus_sabaeus", "Callithrix_jacchus", "Saimiri_sciureus"],
        clade = [fill("great_apes", 4); "lesser_apes"; fill("old_world_monkeys", 4);
                 fill("new_world_monkeys", 2)],
        support = [0.99, 0.97, 0.95, 0.91, 0.88, 0.93, 0.92, 0.85, 0.83, 0.78, 0.75],
    )
    ```

Python methods chain and return the plot; Julia uses mutating functions (`layout!`, `options!`, …) that also return the plot, so calls can be nested or written one per line.

## A rectangular phylogram

<!-- example: 01_rectangular.svg -->
=== "Python"

    ```python
    p = TreePlot(TREE).options(padding=16, px_per_x=1200, px_per_y=24, font_size=12)
    p.save("primates.svg")
    ```

=== "Julia"

    ```julia
    p = TreePlot(TREE)
    options!(p; padding=16, px_per_x=1200, px_per_y=24, font_size=12)
    save(p, "primates.svg")
    ```

![Rectangular phylogram](assets/gallery/01_rectangular.svg)

`px_per_x` is pixels per unit of branch length, `px_per_y` pixels per tip. Tip-label widths are measured from the bundled DejaVu Sans, so the canvas fits the labels exactly.

## Circular layout

<!-- example: 02_circular.svg -->
=== "Python"

    ```python
    p = TreePlot(TREE).layout("circular").options(padding=16, px_per_x=900, font_size=12)
    ```

=== "Julia"

    ```julia
    p = TreePlot(TREE)
    layout!(p, :circular)
    options!(p; padding=16, px_per_x=900, font_size=12)
    ```

![Circular layout](assets/gallery/02_circular.svg)

In the circular layout `px_per_x` sets pixels per unit of branch length along the radius.

## Highlighting a clade

<!-- example: 03_rectangular_highlight.svg -->
=== "Python"

    ```python
    p = (
        TreePlot(TREE)
        .options(padding=16, px_per_x=1200, px_per_y=24, font_size=12)
        .highlight_clade(GREAT_APES, color="#ffb84d", alpha=0.35)
    )
    ```

=== "Julia"

    ```julia
    p = TreePlot(TREE)
    options!(p; padding=16, px_per_x=1200, px_per_y=24, font_size=12)
    highlight_clade!(p, GREAT_APES; color="#ffb84d", alpha=0.35)
    ```

![Great apes highlighted](assets/gallery/03_rectangular_highlight.svg)

The shaded box covers the clade rooted at the most recent common ancestor of the listed tips. In circular layouts it becomes an annular sector.

## Coloring tips by a category

<!-- example: 05_color_tips_by_clade.svg -->
=== "Python"

    ```python
    p = (
        TreePlot(TREE)
        .options(padding=16, px_per_x=1200, px_per_y=24, font_size=12)
        .join_metadata(META, on="tip")
        .color_tips_by("clade")
    )
    ```

=== "Julia"

    ```julia
    p = TreePlot(TREE)
    options!(p; padding=16, px_per_x=1200, px_per_y=24, font_size=12)
    join_metadata!(p, META; on=:tip)
    color_tips_by!(p, :clade)
    ```

![Tips colored by clade](assets/gallery/05_color_tips_by_clade.svg)

Categories get the Tableau-10 palette in order of first appearance down the tree. Pass `palette={"great_apes": "#e15759", ...}` (Julia: `palette=Dict(...)`) to choose colors.

## Coloring branches by a category

<!-- example: 06_color_branches_by_clade.svg -->
=== "Python"

    ```python
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # mixed-clade branches warn; see below
        p = (
            TreePlot(TREE)
            .options(padding=16, px_per_x=1200, px_per_y=24, font_size=12)
            .join_metadata(META, on="tip")
            .color_branches_by("clade")
        )
    ```

=== "Julia"

    ```julia
    p = TreePlot(TREE)
    options!(p; padding=16, px_per_x=1200, px_per_y=24, font_size=12)
    join_metadata!(p, META; on=:tip)
    # Mixed-clade branches log a warning; see below.
    Base.CoreLogging.with_logger(Base.CoreLogging.NullLogger()) do
        color_branches_by!(p, :clade)
    end
    ```

![Branches colored by clade](assets/gallery/06_color_branches_by_clade.svg)

A branch is colored only when every tip below it shares one value. Branches above mixed clades keep the default color and emit a `TreescapeStyleWarning` (Julia: a `@warn` in group `:treescape_style`) naming the branch.

## Coloring by a number

<!-- example: 08_color_branches_by_support.svg -->
=== "Python"

    ```python
    p = (
        TreePlot(TREE)
        .options(padding=16, px_per_x=1200, px_per_y=24, font_size=12)
        .join_metadata(META, on="tip")
        .color_branches_by("support")
    )
    ```

=== "Julia"

    ```julia
    p = TreePlot(TREE)
    options!(p; padding=16, px_per_x=1200, px_per_y=24, font_size=12)
    join_metadata!(p, META; on=:tip)
    color_branches_by!(p, :support)
    ```

![Branches colored by support](assets/gallery/08_color_branches_by_support.svg)

Numeric columns map through viridis. Each branch takes the mean of the tips below it; `vmin` / `vmax` pin the scale. `cmap` also accepts a function `t -> color` — for example a matplotlib colormap wrapped as `lambda t: matplotlib.colors.to_hex(cm(t))`.

## Branch width by a number

<!-- example: 13_branch_width_by_support.svg -->
=== "Python"

    ```python
    p = (
        TreePlot(TREE)
        .options(padding=16, px_per_x=1200, px_per_y=24, font_size=12)
        .join_metadata(META, on="tip")
        .width_branches_by("support")
    )
    ```

=== "Julia"

    ```julia
    p = TreePlot(TREE)
    options!(p; padding=16, px_per_x=1200, px_per_y=24, font_size=12)
    join_metadata!(p, META; on=:tip)
    width_branches_by!(p, :support)
    ```

![Branch width by support](assets/gallery/13_branch_width_by_support.svg)

Widths scale linearly from `wmin=1` to `wmax=4` pixels over the column's range.

## A publication figure

<!-- example: 10_combined.svg -->
=== "Python"

    ```python
    p = (
        TreePlot(TREE)
        .options(padding=16, px_per_x=1200, px_per_y=24, font_size=12)
        .join_metadata(META, on="tip")
        .color_tips_by("clade")
        .highlight_clade(GREAT_APES, color="#ffb84d", alpha=0.25)
        .scale_bar(0.05, "0.05 substitutions/site")
    )
    ```

=== "Julia"

    ```julia
    p = TreePlot(TREE)
    options!(p; padding=16, px_per_x=1200, px_per_y=24, font_size=12)
    join_metadata!(p, META; on=:tip)
    color_tips_by!(p, :clade)
    highlight_clade!(p, GREAT_APES; color="#ffb84d", alpha=0.25)
    scale_bar!(p, 0.05, "0.05 substitutions/site")
    ```

![Combined figure](assets/gallery/10_combined.svg)

## Circular, colored by category

<!-- example: 11_circular_color_tips_by_clade.svg -->
=== "Python"

    ```python
    p = (
        TreePlot(TREE)
        .layout("circular")
        .options(padding=16, px_per_x=900, font_size=12)
        .join_metadata(META, on="tip")
        .color_tips_by("clade")
    )
    ```

=== "Julia"

    ```julia
    p = TreePlot(TREE)
    layout!(p, :circular)
    options!(p; padding=16, px_per_x=900, font_size=12)
    join_metadata!(p, META; on=:tip)
    color_tips_by!(p, :clade)
    ```

![Circular tree colored by clade](assets/gallery/11_circular_color_tips_by_clade.svg)

## A tree from a distance matrix

When all you have are pairwise distances (from an alignment, k-mers, or MATLAB's `seqpdist`), build the tree directly. `method` is neighbor joining (`"nj"`, the default; unrooted, drawn from its last join) or UPGMA (`"upgma"`; rooted, ultrametric). This is the standard neighbor-joining teaching example.

<!-- example: 14_nj_from_distances.svg -->
=== "Python"

    ```python
    D = [[0, 5, 9, 9, 8], [5, 0, 10, 10, 9], [9, 10, 0, 8, 7], [9, 10, 8, 0, 3], [8, 9, 7, 3, 0]]
    p = (
        TreePlot.from_distances(D, ["a", "b", "c", "d", "e"])
        .options(padding=16, px_per_x=40, font_size=12)
        .scale_bar(1.0)
    )
    ```

=== "Julia"

    ```julia
    D = [0 5 9 9 8; 5 0 10 10 9; 9 10 0 8 7; 9 10 8 0 3; 8 9 7 3 0]
    p = TreePlot(D, ["a", "b", "c", "d", "e"])
    options!(p; padding=16, px_per_x=40, font_size=12)
    scale_bar!(p, 1.0)
    ```

![Neighbor-joining tree from a distance matrix](assets/gallery/14_nj_from_distances.svg)

## UPGMA

The same matrix with average linkage gives a rooted, ultrametric tree.

<!-- example: 15_upgma_from_distances.svg -->
=== "Python"

    ```python
    D = [[0, 5, 9, 9, 8], [5, 0, 10, 10, 9], [9, 10, 0, 8, 7], [9, 10, 8, 0, 3], [8, 9, 7, 3, 0]]
    p = (
        TreePlot.from_distances(D, ["a", "b", "c", "d", "e"], method="upgma")
        .options(padding=16, px_per_x=40, font_size=12)
        .scale_bar(1.0)
    )
    ```

=== "Julia"

    ```julia
    D = [0 5 9 9 8; 5 0 10 10 9; 9 10 0 8 7; 9 10 8 0 3; 8 9 7 3 0]
    p = TreePlot(D, ["a", "b", "c", "d", "e"]; method = :upgma)
    options!(p; padding=16, px_per_x=40, font_size=12)
    scale_bar!(p, 1.0)
    ```

![UPGMA tree from the same matrix](assets/gallery/15_upgma_from_distances.svg)

Input checks, the tie rule and how negative neighbor-joining lengths are handled are pinned in [Conventions](conventions.md#trees-from-distance-matrices-v06-phase-3).

## A SciPy linkage matrix

Any other clustering works through a linkage matrix in SciPy's layout: `n − 1` rows of `(cluster_a, cluster_b, distance, count)`, 0-based. Here, complete linkage on the same matrix. Node heights are half the merge distances, so the path between two tips equals their merge distance (SciPy's `dendrogram` draws at the full distance). MATLAB's `linkage` is 1-based with three columns: `[Z(:, 1:2) - 1, Z(:, 3), zeros(size(Z, 1), 1)]` converts it.

<!-- example: 16_from_linkage.svg -->
=== "Python"

    ```python
    from scipy.cluster.hierarchy import linkage
    from scipy.spatial.distance import squareform

    D = [[0, 5, 9, 9, 8], [5, 0, 10, 10, 9], [9, 10, 0, 8, 7], [9, 10, 8, 0, 3], [8, 9, 7, 3, 0]]
    Z = linkage(squareform(D), method="complete")
    p = (
        TreePlot.from_linkage(Z, ["a", "b", "c", "d", "e"])
        .options(padding=16, px_per_x=40, font_size=12)
        .scale_bar(1.0)
    )
    ```

=== "Julia"

    ```julia
    # SciPy's linkage(squareform(D), "complete"), or MATLAB's linkage converted as above.
    Z = [3 4 3 2; 0 1 5 2; 2 5 8 3; 6 7 10 5]
    p = from_linkage(Z, ["a", "b", "c", "d", "e"])
    options!(p; padding=16, px_per_x=40, font_size=12)
    scale_bar!(p, 1.0)
    ```

![Complete-linkage tree from a SciPy linkage matrix](assets/gallery/16_from_linkage.svg)

## From aligned sequences to a dendrogram

Aligned FASTA in, tree out: distances (here Jukes–Cantor), UPGMA, drawn top-down with the tips along the bottom. This is `seqpdist(seqs, 'Alphabet', 'NT')` followed by `seqlinkage` in MATLAB (both default methods; see [Coming from MATLAB](matlab.md)). The data are the cytochrome b genes of the 11 primates, from their RefSeq mitochondrial genomes (accessions in the FASTA headers; `scripts/fetch_primates_cytb.py`). UPGMA recovers the accepted primate tree here. `method="nj"` gives neighbor joining, which does not assume a molecular clock but is unrooted: it is drawn from its last join. Models, gaps and ambiguity codes: [Conventions](conventions.md#distances-from-aligned-sequences-v07-phase-2).

<!-- example: 17_dendrogram_from_sequences.svg -->
=== "Python"

    ```python
    p = (
        TreePlot.from_sequences("tests/fixtures/sequences/primates_cytb.fasta", model="jc69", method="upgma")
        .orientation("down")
        .options(padding=16, px_per_x=1500, px_per_y=24, font_size=12)
        .scale_bar(0.02)
    )
    ```

=== "Julia"

    ```julia
    D, labels = distances("tests/fixtures/sequences/primates_cytb.fasta"; model = :jc69)
    p = TreePlot(D, labels; method = :upgma)
    orientation!(p, :down)
    options!(p; padding=16, px_per_x=1500, px_per_y=24, font_size=12)
    scale_bar!(p, 0.02)
    ```

![UPGMA dendrogram of primate cytochrome b](assets/gallery/17_dendrogram_from_sequences.svg)

`orientation` is `"right"` (the default), `"down"`, `"left"` or `"up"`: the direction the tree grows. Every annotation turns with it ([Conventions](conventions.md#orientation-v07-phase-3)).

## In a notebook

A `TreePlot` displays inline as SVG, no `save` needed: in Jupyter and VS Code notebooks (Python), and in Pluto, IJulia and VS Code (Julia).
