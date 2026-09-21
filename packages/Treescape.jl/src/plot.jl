# The TreePlot grammar. Each method mirrors the same-named method in
# packages/treescape/src/treescape/plot.py so both hosts send identical
# render calls to the Rust core (claim treescape-julia-python-svg-parity).

const _SUPPORTED_LAYOUTS = (:rectangular, :circular)

"""
    TreePlot(source)

A plot of the tree in `source`: an inline Newick string or a path to a
Newick file. Inline if the string contains a newline, ends with `;` or
starts with `(` (after stripping); otherwise a file path. Styling
functions mutate the plot and return it.
"""
mutable struct TreePlot
    tree::Tree
    layout::Symbol
    scene_opts::SceneOptions
    circular_opts::CircularSceneOptions
    highlights::Vector{Tuple{Vector{String},RGBA}}
    tip_colors::Dict{String,RGBA}
    scale_bar::Union{Nothing,Tuple{Float64,String}}
    support_labels::Bool
    support_min::Union{Nothing,Float64}
    metadata_rows::Dict{String,Dict{String,Any}}
    metadata_columns::Set{String}
    branch_colors::Dict{Int,RGBA}
    branch_widths::Dict{Int,Float64}
end

TreePlot(source::AbstractString) = TreePlot(Tree(_newick_text(source)))

"""
    TreePlot(D::AbstractMatrix{<:Real}, labels; method = :nj)

Plot the tree built from a pairwise distance matrix: `method = :nj`
(neighbor joining; unrooted, drawn from its last join) or `:upgma`
(average linkage; rooted, ultrametric). Same conventions and same trees
as Python's `TreePlot.from_distances`.
"""
TreePlot(D::AbstractMatrix{<:Real}, labels::AbstractVector; method::Symbol = :nj) =
    TreePlot(Tree(D, labels; method = method))

"""
    from_linkage(Z, labels) -> TreePlot

Plot the tree in a SciPy-style linkage matrix (`n − 1` rows of
`cluster_a, cluster_b, distance, count`, 0-based cluster indices), as
Python's `TreePlot.from_linkage`. Node heights are half the merge
distances, so the path between two tips equals their merge distance.
MATLAB's `linkage` gives 1-based indices and three columns: use
`[Z[:, 1:2] .- 1 Z[:, 3] zeros(size(Z, 1))]`.
"""
from_linkage(Z::AbstractMatrix{<:Real}, labels::AbstractVector) = TreePlot(Tree(Z, labels, Val(:linkage)))

"""
    to_newick(p) -> String

The plot's tree as a Newick string (also for trees built from distances).
"""
to_newick(p::TreePlot) = newick(p.tree)

function TreePlot(tree::Tree)
    return TreePlot(
        tree,
        :rectangular,
        default_scene_options(),
        default_circular_scene_options(),
        Tuple{Vector{String},RGBA}[],
        Dict{String,RGBA}(),
        nothing,
        false,
        nothing,
        Dict{String,Dict{String,Any}}(),
        Set{String}(),
        Dict{Int,RGBA}(),
        Dict{Int,Float64}(),
    )
end

function _newick_text(source::AbstractString)
    stripped = strip(source)
    looks_like_newick = occursin('\n', source) || endswith(stripped, ';') || startswith(stripped, '(')
    looks_like_newick || return read(source, String)
    # Ambiguous: an existing path that also looks like Newick. Prefer the file.
    isfile(source) && !startswith(stripped, '(') && return read(source, String)
    return String(source)
end

function Base.show(io::IO, p::TreePlot)
    print(io, "TreePlot(", length(p.tree.tip_order), " tips, layout=", p.layout, ")")
end

Base.show(io::IO, ::MIME"image/svg+xml", p::TreePlot) = print(io, to_svg(p))

"""
    layout!(p, kind)

`:rectangular` (default) or `:circular`.
"""
function layout!(p::TreePlot, kind::Union{Symbol,AbstractString})
    kind = Symbol(kind)
    if !(kind in _SUPPORTED_LAYOUTS)
        throw(ArgumentError("supported layouts: $(_SUPPORTED_LAYOUTS); got $(pyrepr(kind))"))
    end
    p.layout = kind
    return p
end

"""
    orientation!(p, direction)

The direction the tree grows, from the root towards the tips: `:right`
(default; root on the left), `:down` (root at the top, a dendrogram),
`:left` or `:up`. Rectangular layout only; rendering a circular plot with
any other value than `:right` is an error. See `docs/conventions.md`,
"Orientation".
"""
function orientation!(p::TreePlot, direction::Union{Symbol,AbstractString})
    code = findfirst(==(Symbol(direction)), ORIENTATIONS)
    code === nothing && throw(ArgumentError(
        "orientation must be one of ('right', 'down', 'left', 'up'), got $(pyrepr(String(direction)))"))
    r = p.scene_opts
    p.scene_opts = SceneOptions(r.px_per_x, r.px_per_y, r.padding, r.font_size, r.label_offset, r.stroke_width,
                                UInt32(code - 1))
    return p
end

"""
    options!(p; px_per_x, px_per_y, padding, font_size, label_offset, stroke_width,
             start_angle, sweep_total)

Override scene options; unspecified values keep their current setting.
`px_per_x` also sets the circular layout's `px_per_r`; `px_per_y` is
rectangular-only. `start_angle` and `sweep_total` (radians; circular only)
make a fan: the first tip points at `start_angle` (default `π/2`) and the
tips sweep clockwise over `sweep_total` (default `2π`, must be in
`(0, 2π]`), keeping their full-circle spacing `sweep_total / N`.
"""
function options!(
    p::TreePlot;
    px_per_x=nothing,
    px_per_y=nothing,
    padding=nothing,
    font_size=nothing,
    label_offset=nothing,
    stroke_width=nothing,
    start_angle=nothing,
    sweep_total=nothing,
)
    # Validate the values as stored (a BigFloat can round to 0 or Inf).
    start_angle = start_angle === nothing ? nothing : Float64(start_angle)
    sweep_total = sweep_total === nothing ? nothing : Float64(sweep_total)
    start_angle === nothing || (isfinite(start_angle) && abs(start_angle) <= 2π) ||
        throw(ArgumentError("start_angle must be in [-2π, 2π], got $(pyfloat(start_angle))"))
    sweep_total === nothing || (isfinite(sweep_total) && 0 < sweep_total <= 2π) ||
        throw(ArgumentError("sweep_total must be finite and in (0, 2π], got $(pyfloat(Float64(sweep_total)))"))
    pick(new, old) = new === nothing ? old : Float64(new)
    r = p.scene_opts
    p.scene_opts = SceneOptions(
        pick(px_per_x, r.px_per_x),
        pick(px_per_y, r.px_per_y),
        pick(padding, r.padding),
        pick(font_size, r.font_size),
        pick(label_offset, r.label_offset),
        pick(stroke_width, r.stroke_width),
        r.orientation,
    )
    c = p.circular_opts
    p.circular_opts = CircularSceneOptions(
        pick(px_per_x, c.px_per_r),
        pick(padding, c.padding),
        pick(font_size, c.font_size),
        pick(label_offset, c.label_offset),
        pick(stroke_width, c.stroke_width),
        pick(start_angle, c.start_angle),
        pick(sweep_total, c.sweep_total),
    )
    return p
end

"""
    highlight_clade!(p, tips; color="#e07b00", alpha=0.3)

Shade the clade rooted at `MRCA(tips)`. `alpha` applies only when
`color` is opaque; an explicit alpha in `color` wins.
"""
function highlight_clade!(p::TreePlot, tips::AbstractVector; color="#e07b00", alpha::Real=0.3)
    isempty(tips) && throw(ArgumentError("highlight_clade requires at least one tip name"))
    r, g, b, a = parse_color(color)
    if a == 0xff && alpha != 1.0
        # Python raises for non-finite alpha (round(inf) / round(nan)).
        isfinite(alpha) || throw(ArgumentError("alpha must be finite; got $alpha"))
        # Clamp before converting so huge finite alphas cannot overflow;
        # rounding is ties-to-even, as Python's round().
        a = UInt8(round(Int, clamp(alpha * 255, 0, 255)))
    end
    push!(p.highlights, (String.(collect(tips)), (r, g, b, a)))
    return p
end

"""
    color_tips!(p, mapping)

Per-tip label colors from `tip_name => color` pairs. Tips not listed
keep the default color.
"""
function color_tips!(p::TreePlot, mapping)
    for (name, spec) in mapping
        p.tip_colors[String(name)] = parse_color(spec)
    end
    return p
end

_missing(v) = v === nothing || v === missing

"""
    join_metadata!(p, table; on)

Join a Tables.jl table onto the tree's tips. `on` names the column whose
values are tip names. Extra rows, duplicate keys and column collisions
are errors; tips absent from the table get missing values.
"""
function join_metadata!(p::TreePlot, table; on::Union{Symbol,AbstractString})
    cols = Tables.columns(table)
    names = String.(collect(Tables.columnnames(cols)))
    on = String(on)
    on in names || throw(ArgumentError("metadata join column $(pyrepr(on)) not found"))

    metadata_columns = [c for c in names if c != on]
    collisions = sort([c for c in metadata_columns if c in p.metadata_columns])
    isempty(collisions) || throw(ArgumentError("metadata column collision(s): $(pyrepr(collisions))"))

    keys = collect(Tables.getcolumn(cols, Symbol(on)))
    tip_names = Set(p.tree.tip_order)
    seen = Set{Any}()
    duplicates = Any[]
    for key in keys
        key in seen && !(key in duplicates) && push!(duplicates, key)
        push!(seen, key)
    end
    isempty(duplicates) || throw(ArgumentError("duplicate metadata key(s): $(pyrepr(duplicates))"))
    extras = [key for key in keys if !(key isa AbstractString && key in tip_names)]
    if !isempty(extras)
        preview = extras[1:min(5, end)]
        throw(ArgumentError(
            "metadata has $(length(extras)) row(s) whose $(pyrepr(on)) value is not a tree tip: $(pyrepr(preview))",
        ))
    end

    columns = Dict(c => collect(Tables.getcolumn(cols, Symbol(c))) for c in metadata_columns)
    row_of = Dict(String(k) => i for (i, k) in enumerate(keys))
    for tip in tip_names
        current = copy(get(p.metadata_rows, tip, Dict{String,Any}()))
        i = get(row_of, tip, nothing)
        for c in metadata_columns
            v = i === nothing ? nothing : columns[c][i]
            current[c] = _missing(v) ? nothing : v
        end
        p.metadata_rows[tip] = current
    end
    union!(p.metadata_columns, metadata_columns)
    return p
end

_value(p::TreePlot, tip, column) = get(get(p.metadata_rows, tip, Dict{String,Any}()), column, nothing)
_observed(p::TreePlot, column) = [v for v in (_value(p, t, column) for t in p.tree.tip_order) if v !== nothing]
_isnumeric(v) = v isa Real && !(v isa Bool)

function _check_column(p::TreePlot, column)
    column = String(column)
    column in p.metadata_columns || throw(ArgumentError("metadata column $(pyrepr(column)) has not been joined"))
    return column
end

function _is_continuous(p::TreePlot, column, palette, cmap)
    cmap !== nothing && return true
    palette !== nothing && return false
    observed = _observed(p, column)
    isempty(observed) && return false
    return all(_isnumeric, observed)
end

function _resolve_cmap(cmap)
    (cmap === nothing || cmap == "viridis" || cmap === :viridis) && return viridis
    cmap isa Union{AbstractString,Symbol} &&
        throw(ArgumentError("unknown cmap $(pyrepr(String(cmap))); built-ins: ['viridis']"))
    # Any callable — a Function or a callable struct — as Python's callable().
    applicable(cmap, 0.5) && return cmap
    throw(ArgumentError("cmap must be a string name or callable; got $(typeof(cmap))"))
end

# Category equality as Python's `==` with its identity shortcut: -0.0
# and 0.0 are one category, as are 1 and 1.0; a NaN matches only itself.
_pyeq(a, b) = a === b || (a == b) === true
_pyfind(values, v) = findfirst(x -> _pyeq(x, v), values)

"""Palette entry for `v`, matching keys the way a Python dict would."""
function _palette_get(palette, v)
    haskey(palette, v) && return palette[v]
    for (k, c) in palette
        _pyeq(k, v) && return c
    end
    throw(KeyError(v))
end
_palette_has(palette, v) = haskey(palette, v) || any(k -> _pyeq(k, v), keys(palette))

_numeric_column(p::TreePlot, column) =
    [(v = _value(p, t, column); v === nothing ? nothing : Float64(v)) for t in p.tree.tip_order]

_range(values, vmin, vmax) =
    value_range(values, vmin === nothing ? nothing : Float64(vmin), vmax === nothing ? nothing : Float64(vmax))

function _distinct_values(p::TreePlot, column)
    values = Any[]
    for tip in p.tree.tip_order
        v = _value(p, tip, column)
        v !== nothing && _pyfind(values, v) === nothing && push!(values, v)
    end
    return values
end

function _resolve_discrete_palette(p::TreePlot, column, palette)
    values = _distinct_values(p, column)
    palette === nothing && return Dict{Any,Any}(zip(values, default_palette(length(values))))
    missing_values = [v for v in values if !_palette_has(palette, v)]
    isempty(missing_values) ||
        throw(ArgumentError("palette missing value(s) for $(pyrepr(column)): $(pyrepr(missing_values))"))
    return palette
end

"""
    color_tips_by!(p, column; palette=nothing, cmap=nothing, vmin=nothing, vmax=nothing)

Color tip labels by a joined metadata column. Numeric columns map
through `cmap` (default viridis; a function `t -> color` also works),
others through `palette` (default Tableau-10 in first-occurrence order).
"""
function color_tips_by!(p::TreePlot, column; palette=nothing, cmap=nothing, vmin=nothing, vmax=nothing)
    column = _check_column(p, column)
    palette !== nothing && cmap !== nothing &&
        throw(ArgumentError("color_tips_by accepts palette= or cmap=, not both"))

    if _is_continuous(p, column, palette, cmap)
        cmap_fn = _resolve_cmap(cmap)
        values = _numeric_column(p, column)
        lo, hi = _range(values, vmin, vmax)
        ts = continuous_tip_t(p.tree, values, lo, hi)
        mapping = [tip => cmap_fn(t) for (tip, t) in zip(p.tree.tip_order, ts) if t !== nothing]
        return color_tips!(p, mapping)
    end

    discrete = _resolve_discrete_palette(p, column, palette)
    mapping = Pair{String,Any}[]
    for tip in p.tree.tip_order
        v = _value(p, tip, column)
        v !== nothing && push!(mapping, tip => _palette_get(discrete, v))
    end
    return color_tips!(p, mapping)
end

_branch_label(p::TreePlot, id) = (name = node_name(p.tree, id); isempty(name) ? "node $id" : name)

"""
    color_branches_by!(p, column; palette=nothing, cmap=nothing, vmin=nothing, vmax=nothing)

Color branches by a joined metadata column. Discrete: a branch is
colored iff all its descendant tips share one value (others warn).
Numeric: the subtree mean maps through `cmap`.
"""
function color_branches_by!(p::TreePlot, column; palette=nothing, cmap=nothing, vmin=nothing, vmax=nothing)
    column = _check_column(p, column)
    palette !== nothing && cmap !== nothing &&
        throw(ArgumentError("color_branches_by accepts palette= or cmap=, not both"))

    # Build into a local map and assign at the end so a failed call leaves
    # prior styling intact (plot.py's atomic-assignment rule).
    if _is_continuous(p, column, palette, cmap)
        cmap_fn = _resolve_cmap(cmap)
        values = _numeric_column(p, column)
        lo, hi = _range(values, vmin, vmax)
        ts = continuous_branch_t(p.tree, values, lo, hi)
        new_colors = Dict{Int,RGBA}()
        for id in p.tree.preorder
            t = ts[id + 1]
            t === nothing || (new_colors[id] = parse_color(cmap_fn(t)))
        end
        p.branch_colors = new_colors
        return p
    end

    discrete = _resolve_discrete_palette(p, column, palette)
    distinct = _distinct_values(p, column)
    codes = map(p.tree.tip_order) do tip
        v = _value(p, tip, column)
        v === nothing ? nothing : _pyfind(distinct, v) - 1
    end
    state, code = discrete_branch_codes(p.tree, codes)
    new_colors = Dict{Int,RGBA}()
    warnings = String[]
    for id in p.tree.preorder
        if state[id + 1] == 1
            new_colors[id] = parse_color(_palette_get(discrete, distinct[code[id + 1] + 1]))
        elseif state[id + 1] == 2
            push!(
                warnings,
                "branch $(_branch_label(p, id)) is not monophyletic for metadata column " *
                "$(pyrepr(column)); leaving default branch color",
            )
        end
    end
    for msg in warnings
        @warn msg _group = :treescape_style
    end
    p.branch_colors = new_colors
    return p
end

"""
    width_branches_by!(p, column; wmin=1.0, wmax=4.0, vmin=nothing, vmax=nothing)

Scale branch stroke widths by a numeric column: subtree mean for
internal branches, the tip's own value for terminal ones.
"""
function width_branches_by!(p::TreePlot, column; wmin::Real=1.0, wmax::Real=4.0, vmin=nothing, vmax=nothing)
    column = _check_column(p, column)
    wlo, whi = Float64(wmin), Float64(wmax)
    isfinite(wlo) && isfinite(whi) ||
        throw(ArgumentError("width_branches_by wmin/wmax must be finite; got ($(pyrepr(wmin)), $(pyrepr(wmax)))"))
    (wlo < 0 || whi < 0) &&
        throw(ArgumentError("width_branches_by wmin/wmax must be non-negative; got ($(pyrepr(wmin)), $(pyrepr(wmax)))"))
    vmin === nothing || isfinite(Float64(vmin)) ||
        throw(ArgumentError("width_branches_by vmin must be finite; got $(pyrepr(vmin))"))
    vmax === nothing || isfinite(Float64(vmax)) ||
        throw(ArgumentError("width_branches_by vmax must be finite; got $(pyrepr(vmax))"))

    observed = _observed(p, column)
    if isempty(observed)
        p.branch_widths = Dict{Int,Float64}()
        return p
    end
    all(_isnumeric, observed) || throw(ArgumentError(
        "width_branches_by($(pyrepr(column))) requires a numeric column; discrete-by-width is out of v0.4 scope",
    ))
    all(v -> isfinite(Float64(v)), observed) || throw(ArgumentError(
        "width_branches_by($(pyrepr(column))) values must be finite; NaN / inf are rejected",
    ))

    values = _numeric_column(p, column)
    lo, hi = _range(values, vmin, vmax)
    widths = branch_widths(p.tree, values, lo, hi, wlo, whi)
    p.branch_widths = Dict(id => w for (id, w) in zip(0:(p.tree.n_nodes - 1), widths) if w !== nothing)
    return p
end

"""
    scale_bar!(p, length, label=nothing)

Branch-length scale bar; the label defaults to the length formatted as
Python would (`0.05`, `1e-05`).
"""
function scale_bar!(p::TreePlot, length::Real, label=nothing)
    length = Float64(length)
    isfinite(length) && length > 0 || throw(ArgumentError("scale_bar length must be positive and finite"))
    p.scale_bar = (length, label === nothing ? pyfloat(length) : pystr(label))
    return p
end

"""
    support_labels!(p; min_value=nothing)

Render internal node names as support labels, optionally only those that
parse as numbers `>= min_value`.
"""
function support_labels!(p::TreePlot; min_value=nothing)
    p.support_labels = true
    p.support_min = min_value === nothing ? nothing : Float64(min_value)
    return p
end

_styled(p::TreePlot) =
    !isempty(p.highlights) || !isempty(p.tip_colors) || !isempty(p.branch_colors) ||
    !isempty(p.branch_widths) || p.scale_bar !== nothing || p.support_labels

function _style_handle(p::TreePlot)
    style = ccall(sym(:ts_style_new), Ptr{Cvoid}, ())
    err = Ref{Ptr{UInt8}}(C_NULL)
    try
        for (tips, (r, g, b, a)) in p.highlights
            GC.@preserve tips begin
                ptrs = [Base.unsafe_convert(Cstring, Base.cconvert(Cstring, t)) for t in tips]
                check(
                    ccall(
                        sym(:ts_style_add_highlight),
                        Int32,
                        (Ptr{Cvoid}, Ptr{Cstring}, Csize_t, UInt8, UInt8, UInt8, UInt8, Ptr{Ptr{UInt8}}),
                        style, ptrs, length(ptrs), r, g, b, a, err,
                    ),
                    err,
                )
            end
        end
        for (name, (r, g, b, a)) in p.tip_colors
            check(
                ccall(
                    sym(:ts_style_set_tip_color),
                    Int32,
                    (Ptr{Cvoid}, Cstring, UInt8, UInt8, UInt8, UInt8, Ptr{Ptr{UInt8}}),
                    style, name, r, g, b, a, err,
                ),
                err,
            )
        end
        for (id, (r, g, b, a)) in p.branch_colors
            check(
                ccall(
                    sym(:ts_style_set_branch_color),
                    Int32,
                    (Ptr{Cvoid}, Csize_t, UInt8, UInt8, UInt8, UInt8, Ptr{Ptr{UInt8}}),
                    style, id, r, g, b, a, err,
                ),
                err,
            )
        end
        for (id, w) in p.branch_widths
            check(
                ccall(sym(:ts_style_set_branch_width), Int32, (Ptr{Cvoid}, Csize_t, Float64, Ptr{Ptr{UInt8}}), style, id, w, err),
                err,
            )
        end
        if p.scale_bar !== nothing
            len, label = p.scale_bar
            check(
                ccall(sym(:ts_style_set_scale_bar), Int32, (Ptr{Cvoid}, Float64, Cstring, Ptr{Ptr{UInt8}}), style, len, label, err),
                err,
            )
        end
        if p.support_labels
            has_min = p.support_min !== nothing
            check(
                ccall(
                    sym(:ts_style_set_support_labels),
                    Int32,
                    (Ptr{Cvoid}, UInt8, Float64, Ptr{Ptr{UInt8}}),
                    style, has_min, has_min ? p.support_min : 0.0, err,
                ),
                err,
            )
        end
    catch
        ccall(sym(:ts_style_free), Cvoid, (Ptr{Cvoid},), style)
        rethrow()
    end
    return style
end

"""
    to_svg(p) -> String

Render the plot to SVG. Byte-deterministic.
"""
function to_svg(p::TreePlot)
    style = _styled(p) ? _style_handle(p) : C_NULL
    out = Ref{Ptr{UInt8}}(C_NULL)
    err = Ref{Ptr{UInt8}}(C_NULL)
    try
        status = if p.layout === :rectangular
            opts = Ref(p.scene_opts)
            ccall(
                sym(:ts_render_rectangular_svg),
                Int32,
                (Ptr{Cvoid}, Ptr{SceneOptions}, Ptr{Cvoid}, Ptr{Ptr{UInt8}}, Ptr{Ptr{UInt8}}),
                p.tree, opts, style, out, err,
            )
        else
            if p.scene_opts.orientation != 0
                o = ORIENTATIONS[p.scene_opts.orientation + 1]
                throw(ArgumentError("orientation $(pyrepr(String(o))) applies to the rectangular layout only; " *
                                    "the circular layout's direction is set by start_angle and sweep_total"))
            end
            opts = Ref(p.circular_opts)
            ccall(
                sym(:ts_render_circular_svg),
                Int32,
                (Ptr{Cvoid}, Ptr{CircularSceneOptions}, Ptr{Cvoid}, Ptr{Ptr{UInt8}}, Ptr{Ptr{UInt8}}),
                p.tree, opts, style, out, err,
            )
        end
        check(status, err)
        return take_string!(out[])
    finally
        style == C_NULL || ccall(sym(:ts_style_free), Cvoid, (Ptr{Cvoid},), style)
    end
end

"""
    save(p, path)

Render and write the SVG to `path`. Returns the plot.
"""
function save(p::TreePlot, path::AbstractString)
    write(path, to_svg(p))
    return p
end
