# Julia driver for claim treescape-julia-python-svg-parity.
#
#   julia --project=packages/Treescape.jl packages/Treescape.jl/test/parity_runner.jl \
#       tests/fixtures/parity/cases.toml <repo root> <output dir>
#
# Interprets every case in the TOML file with Treescape.jl and writes
# `<output dir>/<case name>.svg`; tests/oracle/test_julia_parity.py
# compares them with the Python package's output. Prints `DONE <n>` last.

using TOML
using Treescape

const COLOR_KEYS = ("color",)

tuplify(x) = x isa AbstractVector && all(v -> v isa Real, x) ? Tuple(x) : x

function table(spec::AbstractDict)
    # Column order does not matter for joins; sort for determinism.
    cols = sort(collect(keys(spec)))
    return NamedTuple{Tuple(Symbol.(cols))}(Tuple(collect(spec[c]) for c in cols))
end

function convert_arg(op, i, arg, tables)
    op == "join_metadata" && i == 1 && return table(tables[arg])
    op == "color_tips" && i == 1 && return Dict(k => tuplify(v) for (k, v) in arg)
    return arg
end

function convert_kwarg(k, v)
    k in COLOR_KEYS && return tuplify(v)
    k == "palette" && return Dict{Any,Any}(pv => tuplify(c) for (pv, c) in v)
    return v
end

function run_case(case, trees, tables, repo)
    source = trees[case["tree"]]
    p = if haskey(source, "sequences")
        D, labels = distances(joinpath(repo, source["sequences"]); model = Symbol(source["model"]),
                                alphabet = Symbol(get(source, "alphabet", "auto")))
        TreePlot(D, labels; method = Symbol(source["method"]))
    elseif haskey(source, "linkage")
        from_linkage(permutedims(reduce(hcat, [Float64.(row) for row in source["linkage"]])), source["labels"])
    elseif haskey(source, "distances")
        lines = readlines(joinpath(repo, source["distances"]))
        D = permutedims(reduce(hcat, [parse.(Float64, split(l, '\t')) for l in lines[2:end]]))
        TreePlot(D, split(lines[1], '\t'); method = Symbol(source["method"]))
    else
        TreePlot(haskey(source, "path") ? joinpath(repo, source["path"]) : source["newick"])
    end
    for step in case["ops"]
        op = step["op"]
        args = [convert_arg(op, i, a, tables) for (i, a) in enumerate(get(step, "args", []))]
        kwargs = Dict(Symbol(k) => convert_kwarg(k, v) for (k, v) in get(step, "kwargs", Dict()))
        fn = getfield(Treescape, Symbol(op, "!"))
        fn(p, args...; kwargs...)
    end
    return to_svg(p)
end

function main(cases_path, repo, outdir)
    spec = TOML.parsefile(cases_path)
    mkpath(outdir)
    n = 0
    for case in spec["cases"]
        println("CASE ", case["name"])
        flush(stdout)
        write(joinpath(outdir, case["name"] * ".svg"), run_case(case, spec["trees"], spec["tables"], repo))
        n += 1
    end
    println("DONE ", n)
end

main(ARGS...)
