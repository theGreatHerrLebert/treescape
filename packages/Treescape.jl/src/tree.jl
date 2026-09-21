# Tree handle and the styling resolvers (treescape_core::style).

"""
    Tree

A parsed tree owned by the Rust core. Node ids are 0-based, as on the C
side; structure is cached on construction.
"""
mutable struct Tree
    ptr::Ptr{Cvoid}
    n_nodes::Int
    root::Int
    preorder::Vector{Int}
    is_tip::Vector{Bool}
    names::Vector{String}
    tip_order::Vector{String}
end

function Tree(newick::AbstractString)
    out = Ref{Ptr{Cvoid}}(C_NULL)
    err = Ref{Ptr{UInt8}}(C_NULL)
    status = ccall(
        sym(:ts_tree_parse_newick),
        Int32,
        (Cstring, Ptr{Ptr{Cvoid}}, Ptr{Ptr{UInt8}}),
        newick,
        out,
        err,
    )
    check(status, err)
    tree = Tree(out[], 0, -1, Int[], Bool[], String[], String[])
    # Resolve the pointer now so the finalizer does no lookup at GC time.
    free = sym(:ts_tree_free)
    finalizer(t -> ccall(free, Cvoid, (Ptr{Cvoid},), t.ptr), tree)
    _fill_caches!(tree)
    return tree
end

# Passing the `Tree` itself (not `tree.ptr`) to `ccall` roots it for the
# duration of the call, so its finalizer cannot free the handle mid-call.
Base.unsafe_convert(::Type{Ptr{Cvoid}}, t::Tree) = t.ptr

# A Tree is never mutated after construction, so copies share the owner.
# Copying the raw pointer would give two finalizers one handle.
Base.deepcopy_internal(t::Tree, ::IdDict) = t
Base.copy(t::Tree) = t

function _size(tree::Tree, fn::Symbol)
    out = Ref{Csize_t}(0)
    err = Ref{Ptr{UInt8}}(C_NULL)
    check(ccall(sym(fn), Int32, (Ptr{Cvoid}, Ptr{Csize_t}, Ptr{Ptr{UInt8}}), tree, out, err), err)
    return Int(out[])
end

function _string(tree::Tree, fn::Symbol, i::Integer)
    out = Ref{Ptr{UInt8}}(C_NULL)
    err = Ref{Ptr{UInt8}}(C_NULL)
    status = ccall(
        sym(fn),
        Int32,
        (Ptr{Cvoid}, Csize_t, Ptr{Ptr{UInt8}}, Ptr{Ptr{UInt8}}),
        tree,
        i,
        out,
        err,
    )
    check(status, err)
    return take_string!(out[])
end

function _fill_caches!(tree::Tree)
    n = _size(tree, :ts_tree_n_nodes)
    tree.n_nodes = n
    n == 0 && return tree
    tree.root = _size(tree, :ts_tree_root)
    buf = zeros(Csize_t, n)
    len = Ref{Csize_t}(0)
    err = Ref{Ptr{UInt8}}(C_NULL)
    status = ccall(
        sym(:ts_tree_preorder),
        Int32,
        (Ptr{Cvoid}, Ptr{Csize_t}, Csize_t, Ptr{Csize_t}, Ptr{Ptr{UInt8}}),
        tree,
        buf,
        n,
        len,
        err,
    )
    check(status, err)
    tree.preorder = Int.(buf[1:len[]])
    tree.names = [_string(tree, :ts_tree_node_name, i) for i in 0:(n - 1)]
    tree.is_tip = map(0:(n - 1)) do i
        out = Ref{UInt8}(0)
        e = Ref{Ptr{UInt8}}(C_NULL)
        check(
            ccall(sym(:ts_tree_is_tip), Int32, (Ptr{Cvoid}, Csize_t, Ptr{UInt8}, Ptr{Ptr{UInt8}}), tree, i, out, e),
            e,
        )
        out[] != 0
    end
    n_tips = _size(tree, :ts_tree_n_tips)
    tree.tip_order = [_string(tree, :ts_tree_tip_name, k) for k in 0:(n_tips - 1)]
    return tree
end

node_name(tree::Tree, id::Integer) = tree.names[id + 1]
is_tip(tree::Tree, id::Integer) = tree.is_tip[id + 1]

# --- resolvers -------------------------------------------------------------

"""Built-in viridis color for `t` as an RGBA tuple."""
function viridis(t::Real)
    out = zeros(UInt8, 4)
    err = Ref{Ptr{UInt8}}(C_NULL)
    check(ccall(sym(:ts_viridis), Int32, (Float64, Ptr{UInt8}, Ptr{Ptr{UInt8}}), t, out, err), err)
    return (out[1], out[2], out[3], out[4])
end

"""Tableau-10 colors for `n` distinct values (more than 10 is an error)."""
function default_palette(n::Integer)
    n < 0 && throw(ArgumentError("palette size must be a non-negative integer; got $n"))
    out = zeros(UInt8, 4n)
    err = Ref{Ptr{UInt8}}(C_NULL)
    check(ccall(sym(:ts_default_palette), Int32, (Csize_t, Ptr{UInt8}, Ptr{Ptr{UInt8}}), n, out, err), err)
    return [(out[4k + 1], out[4k + 2], out[4k + 3], out[4k + 4]) for k in 0:(n - 1)]
end

"""Split a column of `Union{Nothing,Float64}` into values + presence mask."""
function _split(values::AbstractVector)
    present = UInt8[v === nothing ? 0 : 1 for v in values]
    vals = Float64[v === nothing ? 0.0 : Float64(v) for v in values]
    return vals, present
end

function value_range(values::AbstractVector, vmin, vmax)
    vals, present = _split(values)
    lo = Ref{Float64}(0)
    hi = Ref{Float64}(0)
    err = Ref{Ptr{UInt8}}(C_NULL)
    status = ccall(
        sym(:ts_value_range),
        Int32,
        (Ptr{Float64}, Ptr{UInt8}, Csize_t, UInt8, Float64, UInt8, Float64, Ptr{Float64}, Ptr{Float64}, Ptr{Ptr{UInt8}}),
        vals,
        present,
        length(vals),
        vmin !== nothing,
        vmin === nothing ? 0.0 : Float64(vmin),
        vmax !== nothing,
        vmax === nothing ? 0.0 : Float64(vmax),
        lo,
        hi,
        err,
    )
    check(status, err)
    return lo[], hi[]
end

"""Per-tip `t` aligned to tip order (`nothing` where the tip has no value)."""
function continuous_tip_t(tree::Tree, values::AbstractVector, lo::Float64, hi::Float64)
    vals, present = _split(values)
    n = length(vals)
    out_t = zeros(Float64, n)
    out_has = zeros(UInt8, n)
    err = Ref{Ptr{UInt8}}(C_NULL)
    status = ccall(
        sym(:ts_continuous_tip_t),
        Int32,
        (Ptr{Cvoid}, Ptr{Float64}, Ptr{UInt8}, Csize_t, Float64, Float64, Ptr{Float64}, Ptr{UInt8}, Ptr{Ptr{UInt8}}),
        tree,
        vals,
        present,
        n,
        lo,
        hi,
        out_t,
        out_has,
        err,
    )
    check(status, err)
    return [out_has[k] != 0 ? out_t[k] : nothing for k in 1:n]
end

"""Per-node results (indexed by `id + 1`; `nothing` = keep default)."""
function _per_node(tree::Tree, fn::Symbol, values::AbstractVector, extra::Vararg{Float64})
    vals, present = _split(values)
    out = zeros(Float64, tree.n_nodes)
    out_has = zeros(UInt8, tree.n_nodes)
    err = Ref{Ptr{UInt8}}(C_NULL)
    status = if fn === :ts_continuous_branch_t
        ccall(
            sym(fn),
            Int32,
            (Ptr{Cvoid}, Ptr{Float64}, Ptr{UInt8}, Csize_t, Float64, Float64, Ptr{Float64}, Ptr{UInt8}, Ptr{Ptr{UInt8}}),
            tree, vals, present, length(vals), extra[1], extra[2], out, out_has, err,
        )
    else
        ccall(
            sym(fn),
            Int32,
            (Ptr{Cvoid}, Ptr{Float64}, Ptr{UInt8}, Csize_t, Float64, Float64, Float64, Float64, Ptr{Float64}, Ptr{UInt8}, Ptr{Ptr{UInt8}}),
            tree, vals, present, length(vals), extra[1], extra[2], extra[3], extra[4], out, out_has, err,
        )
    end
    check(status, err)
    return [out_has[k] != 0 ? out[k] : nothing for k in 1:(tree.n_nodes)]
end

continuous_branch_t(tree::Tree, values, lo::Float64, hi::Float64) =
    _per_node(tree, :ts_continuous_branch_t, values, lo, hi)

branch_widths(tree::Tree, values, lo::Float64, hi::Float64, wmin::Float64, wmax::Float64) =
    _per_node(tree, :ts_branch_widths, values, lo, hi, wmin, wmax)

"""
Monophyly rule over 0-based codes aligned to tip order. Returns per-node
`(state, code)` with state `0` default, `1` colored, `2` non-monophyletic.
"""
function discrete_branch_codes(tree::Tree, codes::AbstractVector)
    present = UInt8[c === nothing ? 0 : 1 for c in codes]
    vals = UInt32[c === nothing ? 0 : c for c in codes]
    out_code = zeros(UInt32, tree.n_nodes)
    out_state = zeros(UInt8, tree.n_nodes)
    err = Ref{Ptr{UInt8}}(C_NULL)
    status = ccall(
        sym(:ts_discrete_branch_codes),
        Int32,
        (Ptr{Cvoid}, Ptr{UInt32}, Ptr{UInt8}, Csize_t, Ptr{UInt32}, Ptr{UInt8}, Ptr{Ptr{UInt8}}),
        tree,
        vals,
        present,
        length(vals),
        out_code,
        out_state,
        err,
    )
    check(status, err)
    return out_state, out_code
end
