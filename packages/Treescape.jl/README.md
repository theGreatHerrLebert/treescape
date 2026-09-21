# Treescape.jl

Julia bindings for [treescape](../../README.md): phylogenetic tree plots
with deterministic SVG output, drawn by the same Rust core as the Python
package. For the same inputs, `Treescape.jl` and Python's `treescape`
produce byte-identical SVG (EVIDENT claim
`treescape-julia-python-svg-parity`).

Architecture follows rustims' `imsjl_connector` / `IMSJL`: a C-ABI
cdylib (`treescape-jl-connector`) called through `ccall`.

## Install (development)

The connector library is not yet shipped as a JLL; build it from a
checkout of the treescape repository:

```bash
cargo build -p treescape-jl-connector --release
julia --project=packages/Treescape.jl -e 'using Pkg; Pkg.instantiate()'
```

`Treescape.jl` finds the library through `ENV["TREESCAPE_JL_LIB"]`, then
the `libpath` preference (`Treescape.set_library!(path)`), then
`target/release/` of the checkout it lives in.

Requires Julia ≥ 1.10 (tested on 1.10 and 1.12).

## Usage

```julia
using Treescape

p = TreePlot("tests/fixtures/trees/medium/primates.nwk")
options!(p; padding=16, px_per_x=1200, px_per_y=24, font_size=12)
highlight_clade!(p, ["Homo_sapiens", "Pan_troglodytes", "Gorilla_gorilla", "Pongo_abelii"];
                 color="#ffb84d", alpha=0.35)
save(p, "primates.svg")
```

Metadata comes from any Tables.jl source (a `DataFrame`, a `CSV.File`,
or a `NamedTuple` of vectors):

```julia
meta = (tip = ["Homo_sapiens", "Pan_troglodytes"], clade = ["great_apes", "great_apes"])

p = TreePlot("tests/fixtures/trees/medium/primates.nwk")
layout!(p, :circular)
join_metadata!(p, meta; on=:tip)
color_tips_by!(p, :clade)                      # Tableau-10, first-occurrence order
color_branches_by!(p, :clade)                  # monophyletic branches only; others @warn
scale_bar!(p, 0.05, "0.05 subs/site")
```

In a notebook (Pluto, IJulia, VS Code) a `TreePlot` displays inline as
SVG.

| Function | Python equivalent |
|---|---|
| `TreePlot(source)` | `TreePlot(source)` |
| `layout!(p, :circular)` | `.layout("circular")` |
| `options!(p; px_per_x, px_per_y, padding, font_size, label_offset, stroke_width)` | `.options(...)` |
| `highlight_clade!(p, tips; color, alpha)` | `.highlight_clade(...)` |
| `color_tips!(p, mapping)` | `.color_tips(...)` |
| `join_metadata!(p, table; on)` | `.join_metadata(df, on=...)` |
| `color_tips_by!(p, col; palette, cmap, vmin, vmax)` | `.color_tips_by(...)` |
| `color_branches_by!(p, col; palette, cmap, vmin, vmax)` | `.color_branches_by(...)` |
| `width_branches_by!(p, col; wmin, wmax, vmin, vmax)` | `.width_branches_by(...)` |
| `scale_bar!(p, length, label)` | `.scale_bar(...)` |
| `support_labels!(p; min_value)` | `.support_labels(...)` |
| `to_svg(p)`, `save(p, path)` | `.to_svg()`, `.save(path)` |

`cmap` accepts `"viridis"` (default) or a function `t -> color`. Colors
are `"#rrggbb"`, `"#rrggbbaa"`, or 3-/4-tuples of 0–255 integers.

Where the Julia host layer mirrors Python (source heuristic, color
parsing, alpha rounding, numeric detection, label formatting), the rules
are listed in `docs/conventions.md`, section "Julia binding (v0.5
Phase 2)".
