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

## In a notebook

In Julia a `TreePlot` displays inline as SVG in Pluto, IJulia and VS Code — no `save` needed. In Jupyter (Python), display the string `to_svg()` returns: `IPython.display.SVG(p.to_svg())`.
