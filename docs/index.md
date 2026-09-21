# treescape

Phylogenetic tree plots with deterministic SVG output, a Rust core, and bindings for **Python** and **Julia**. Every numerical and structural claim the library makes is pinned in a trust manifest with an oracle (an external tool where one exists), a tolerance, and the command that checks it.

![Rectangular phylogram of 11 primates](assets/primates.svg)

## What you get

- **Layouts:** rectangular and circular phylograms, laid out from branch lengths. Both the Rust core and the readable Python reference agree with ete3, Biopython.Phylo and R/ggtree (rectangular) and with ete3 and R/ggtree (circular) on 66 trees of 2–200 tips, node by node wherever the oracle defines the node; where they differ, [Conventions](conventions.md) says how and why.
- **Styling from metadata:** join a table on tip names, then color tips and branches by category (Tableau-10) or number (viridis), scale branch widths, highlight clades, and add scale bars and support labels.
- **Deterministic output:** the same inputs give byte-identical SVG, in Python and in Julia alike (verified on Linux).
- **Trust you can check:** the [claims](claims.md) page lists every EVIDENT claim, its oracle, and the command that verifies it.

## Install (development)

treescape is not yet on PyPI or the Julia General registry. From a checkout:

=== "Python"

    ```bash
    git clone https://github.com/theGreatHerrLebert/treescape.git
    cd treescape
    python3.12 -m venv .venv && source .venv/bin/activate
    pip install maturin polars
    pip install -e ./treescape-connector -e packages/treescape-reference -e packages/treescape
    ```

=== "Julia"

    ```bash
    git clone https://github.com/theGreatHerrLebert/treescape.git
    cd treescape
    cargo build -p treescape-jl-connector --release
    julia --project=packages/Treescape.jl -e 'using Pkg; Pkg.instantiate()'
    ```

    Julia ≥ 1.10. See the [Julia package](julia.md) page for how the library is located.

## Quickstart

=== "Python"

    ```python
    from treescape import TreePlot

    TreePlot("((a:1,b:1):1,(c:1,d:1):1);").layout("circular").save("tree.svg")
    ```

=== "Julia"

    ```julia
    using Treescape

    p = TreePlot("((a:1,b:1):1,(c:1,d:1):1);")
    layout!(p, :circular)
    save(p, "tree.svg")
    ```

Continue with the [examples](examples.md), which are tested to reproduce the images they show in both languages.

## Architecture

```text
Rust:    treescape-core/  (tree, Newick, layout, styling rules)   treescape-render/  (SVG)
PyO3:    treescape-connector/      →  Python: packages/treescape, packages/treescape-reference
C ABI:   treescape-jl-connector/   →  Julia:  packages/Treescape.jl
```

The layout mirrors [rustims](https://github.com/theGreatHerrLebert/rustims): one Rust core, a PyO3 connector for Python and a C-ABI connector for Julia. `treescape-reference` is a slow, readable Python implementation that the Rust core is held to — the oracle is written before the code.
