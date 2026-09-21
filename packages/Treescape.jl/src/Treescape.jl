"""
    Treescape

Phylogenetic tree plots with deterministic SVG output, driven by the
treescape Rust core through the `treescape-jl-connector` C ABI.

```julia
using Treescape

p = TreePlot("((a:1,b:1):1,(c:1,d:1):1);")
layout!(p, :circular)
save(p, "tree.svg")
```

Output is byte-identical to the Python `treescape` package for the same
inputs (EVIDENT claim `treescape-julia-python-svg-parity`).
"""
module Treescape

using Artifacts
using Libdl
import Pkg
using Preferences
using Tables

export TreePlot,
    layout!,
    options!,
    orientation!,
    highlight_clade!,
    color_tips!,
    join_metadata!,
    color_tips_by!,
    color_branches_by!,
    width_branches_by!,
    scale_bar!,
    support_labels!,
    to_svg,
    to_newick,
    from_linkage,
    distances,
    save

include("lib.jl")
include("tree.jl")
include("colors.jl")
include("plot.jl")
include("seq.jl")

end
