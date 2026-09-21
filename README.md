# treescape

Phylogenetic tree figures for **Python** and **Julia**: one Rust core, byte-deterministic SVG, and layouts checked against ete3, Biopython and ggtree.

<p align="center">
  <img src="assets/primates.svg" alt="treescape rendering of an 11-tip primate phylogeny" width="640"/>
</p>

**Docs, tested examples and the full claim list:** <https://thegreatherrlebert.github.io/treescape/>

## Why

R has [ggtree](https://bioconductor.org/packages/ggtree/): join a table onto a tree, map columns to colors, widths and highlights, get a publication figure. Python and Julia have good tools with narrower scope — [ete3](https://github.com/etetoolkit/ete) (GPL, Qt-based rendering), Biopython's `Bio.Phylo.draw` (matplotlib, basic styling), [toytree](https://github.com/eaton-lab/toytree) (the closest Python equivalent), and in Julia [Phylo.jl](https://github.com/EcoJulia/Phylo.jl)'s Plots recipes and [PhyloPlots.jl](https://github.com/JuliaPhylo/PhyloPlots.jl). None of them combines

- **metadata-driven styling** — color tips and branches by a category or a number, scale branch widths, highlight clades;
- **reproducible output** — the same input gives the same SVG bytes, so figures can be diffed and pinned in CI;
- **checked geometry** — layout coordinates compared against independent tools, with every deliberate difference documented;
- **one implementation for two languages** — Python and Julia call the same Rust core and produce identical files.

treescape is built to fill that gap.

## Quickstart

**Install** (from v0.7.0; no Rust toolchain needed). Prebuilt for Linux (x86-64, aarch64), macOS (arm64, x86-64) and Windows (x86-64):

```bash
pip install treescape                     # Python ≥ 3.11
```

```julia
using Pkg                                 # Julia ≥ 1.10; downloads the prebuilt library on first use
Pkg.add(url = "https://github.com/theGreatHerrLebert/treescape", subdir = "packages/Treescape.jl", rev = "v0.7.0")
```

To work on treescape itself, build from a checkout instead (see [`.github/CONTRIBUTING.md`](.github/CONTRIBUTING.md)).

**Python**

```python
import polars as pl
from treescape import TreePlot

meta = pl.DataFrame({"tip": ["a", "b", "c", "d"], "clade": ["x", "x", "y", "y"]})

(TreePlot("((a:1,b:1):1,(c:1,d:1):1);")
    .layout("circular")
    .join_metadata(meta, on="tip")
    .color_tips_by("clade")
    .save("tree.svg"))
```

**Julia** (≥ 1.10)

```bash
cargo build -p treescape-jl-connector --release
julia --project=packages/Treescape.jl -e 'using Pkg; Pkg.instantiate()'
```

```julia
using Treescape

meta = (tip = ["a", "b", "c", "d"], clade = ["x", "x", "y", "y"])   # or a DataFrame

p = TreePlot("((a:1,b:1):1,(c:1,d:1):1);")
layout!(p, :circular)
join_metadata!(p, meta; on=:tip)
color_tips_by!(p, :clade)
save(p, "tree.svg")        # identical bytes to the Python file
```

More: the [examples](https://thegreatherrlebert.github.io/treescape/examples/) (both languages, each tested against the image it shows) and the [gallery](assets/gallery/).

## What to trust

Every correctness claim is pinned in [`evident.yaml`](evident.yaml) — the [EVIDENT](https://github.com/theGreatHerrLebert/evident) trust manifest — with an oracle, a tolerance, and the command that checks it. The [claims page](https://thegreatherrlebert.github.io/treescape/claims/) renders all of them.

| What | Checked against | Tolerance |
|---|---|---|
| Newick parsing (Python reference and Rust parsers) | Biopython | exact topology (every clade); every branch length 1e-9 |
| Rectangular layout (Rust core and Python reference, every node) | ete3, Biopython, R/ggtree | 1e-6 (ggtree 1e-4) |
| Circular layout (Rust core and Python reference) | ete3, R/ggtree | 1e-6 (ggtree 1e-3) in (r, θ) |
| Rust core vs readable Python reference | `treescape-reference` | 1e-9 layout; exact styling rules |
| Trees from distance matrices: neighbor joining | scikit-bio, Biopython, R/ape; and recovery of the true tree from exact tree distances | exact splits; edge lengths 1e-9 |
| Trees from distance matrices: UPGMA | SciPy, R/phangorn | exact clades; heights 1e-9 |
| Distances from aligned sequences (p, JC69, K2P; protein p, JC69, Poisson) | scikit-bio, R/ape; hand-computed protein values | 1e-12 per pair |
| Orientation (dendrograms: root at the top, bottom, left or right) | the validated rectangular layout under the documented transform; the Python reference | exact, every branch and tip label |
| Installed packages, all five platforms | the committed gallery | byte-identical |
| Label widths | fontTools reading the same font | 0.5 px |
| Python ↔ Julia output | each other, and every gallery file | byte-identical |
| Julia boundary | ~1,600 hostile and fuzzed inputs; Miri | never aborts the process |

Where the external tools disagree with each other or with treescape — sweep direction, default ladderization, y offsets — the difference is documented in [conventions](docs/conventions.md), not hidden in a tolerance.

**Known limits of that evidence**, stated plainly: external layout agreement is established on 66 trees of 2–200 tips (hand-written fixtures plus a pinned random corpus with multifurcations, zero-length branches and ladders), not on large real-world trees; rendered SVG geometry is snapshot-tested rather than checked against the validated coordinates; byte determinism is verified on every published platform (Linux x86-64/aarch64, macOS arm64/x86-64, Windows x86-64); branch styling is O(nodes × depth); neighbor joining is exact O(n³) and slower than scikit-bio's (see the [performance page](https://thegreatherrlebert.github.io/treescape/performance/)).

## Design philosophy

- **One implementation, many hosts.** Layout, styling rules and SVG emission live in Rust. Python and Julia add only host concerns (data frames, color parsing, warnings) and are held to byte-identical output.
- **Oracle first.** A slow, readable Python reference is written before the Rust port and stays as the oracle; external tools from independent lineages check the reference. A claim is pinned before the code that backs it.
- **Document disagreement, don't absorb it.** Convention gaps between tools are written down; tolerances are never widened to make a test pass.
- **Deterministic by construction.** Fixed float formatting, sorted attributes, no timestamps, a bundled font for text measurement.
- **Tight scope.** Newick in, SVG out, two layouts, metadata-driven styling. No matplotlib, no GUI.

## Repo shape

```text
treescape-core/          tree model, Newick, layouts, styling rules (Rust)
treescape-render/        deterministic SVG emitter + bundled DejaVu Sans (Rust)
treescape-connector/     PyO3 bindings        → packages/treescape            (Python)
treescape-jl-connector/  C-ABI bindings       → packages/Treescape.jl         (Julia)
packages/treescape-reference/   readable Python reference: the oracle for the Rust core
tests/oracle/            one runner per EVIDENT claim
docs/, mkdocs.yml        documentation site
```

The layout follows [rustims](https://github.com/theGreatHerrLebert/rustims): a Rust workspace with a PyO3 connector for Python and a C-ABI connector for Julia.

## Acknowledgements

treescape contains **no code** from the tools below. Its layout conventions and styling semantics were designed against their published behavior, and several of them serve as test oracles.

- **Layout conventions and oracles:** ete3 (Huerta-Cepas et al.), Bio.Phylo (Talevich et al., Biopython), ggtree (Yu et al.). Test-only; not linked or redistributed. ete3 is GPL-3.0 and is imported only by the test suite.
- **Ladderization** follows the tip-count ordering popularized by ape's `ladderize` (Paradis & Schliep).
- **Newick** follows Felsenstein's PHYLIP specification.
- **viridis** keystops sample matplotlib's viridis (van der Walt & Smith; CC0). **Tableau 10** palette values by Maureen Stone (Tableau Software).
- **Subtree means** use Neumaier-compensated summation (Neumaier 1974), matching CPython ≥ 3.12's `sum()`.
- **Bundled font:** DejaVu Sans (Bitstream Vera Fonts License).
- **Built with** PyO3, fontdue, polars, fontTools, Tables.jl and Preferences.jl; tested with Hypothesis and Miri.

Licenses for everything bundled, linked, reproduced or tested against are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## References

- Huerta-Cepas, Serra & Bork. "ETE 3: Reconstruction, Analysis, and Visualization of Phylogenomic Data." *Mol Biol Evol* 33(6), 1635–1638 (2016). https://doi.org/10.1093/molbev/msw046
- Talevich, Invergo, Cock & Chapman. "Bio.Phylo: A unified toolkit for processing, analyzing and visualizing phylogenetic trees in Biopython." *BMC Bioinformatics* 13, 209 (2012). https://doi.org/10.1186/1471-2105-13-209
- Cock et al. "Biopython: freely available Python tools for computational molecular biology and bioinformatics." *Bioinformatics* 25(11), 1422–1423 (2009). https://doi.org/10.1093/bioinformatics/btp163
- Yu, Smith, Zhu, Guan & Lam. "ggtree: an R package for visualization and annotation of phylogenetic trees with their covariates and other associated data." *Methods Ecol Evol* 8(1), 28–36 (2017). https://doi.org/10.1111/2041-210X.12628
- Paradis & Schliep. "ape 5.0: an environment for modern phylogenetics and evolutionary analyses in R." *Bioinformatics* 35(3), 526–528 (2019). https://doi.org/10.1093/bioinformatics/bty633
- Eaton. "Toytree: A minimalist tree visualization and manipulation library for Python." *Methods Ecol Evol* 11(1), 187–191 (2020). https://doi.org/10.1111/2041-210X.13313
- Felsenstein. "The Newick tree format." PHYLIP documentation. https://evolution.genetics.washington.edu/phylip/newicktree.html
- Neumaier. "Rundungsfehleranalyse einiger Verfahren zur Summation endlicher Summen." *ZAMM* 54(1), 39–51 (1974). https://doi.org/10.1002/zamm.19740540106
- MacIver, Hatfield-Dodds et al. "Hypothesis: A new approach to property-based testing." *JOSS* 4(43), 1891 (2019). https://doi.org/10.21105/joss.01891

## License

MIT — see [LICENSE](LICENSE). Third-party notices, including the DejaVu Sans font license, are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
