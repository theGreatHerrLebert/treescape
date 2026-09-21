# C-ABI loading and error plumbing (docs/conventions.md, "Julia binding").

const ABI_VERSION = UInt32(1)

const TS_OK = Int32(0)
const TS_INVALID_ARGUMENT = Int32(1)
const TS_PARSE_ERROR = Int32(2)
const TS_STYLE_ERROR = Int32(3)
const TS_RENDER_ERROR = Int32(4)

"""
    TreescapeError(code, msg)

Raised when the Rust core reports an error: `code` is the C-ABI status
(`2` parse, `3` styling, `4` render); `msg` is the same text Python's
exception carries. Invalid arguments raise `ArgumentError` instead.
"""
struct TreescapeError <: Exception
    code::Int32
    msg::String
end

Base.showerror(io::IO, e::TreescapeError) = print(io, "TreescapeError: ", e.msg)

const _HANDLE = Ref{Ptr{Cvoid}}(C_NULL)
const _LOCK = ReentrantLock()

# Every entry point, resolved once when the library loads. After that the
# table is only read, so `sym` needs no lock (and is safe in finalizers).
const _SYMBOL_NAMES = (
    :ts_abi_version, :ts_string_free,
    :ts_tree_parse_newick, :ts_tree_free, :ts_tree_n_nodes, :ts_tree_n_tips, :ts_tree_root,
    :ts_tree_preorder, :ts_tree_is_tip, :ts_tree_node_name, :ts_tree_tip_name,
    :ts_style_new, :ts_style_free, :ts_style_add_highlight, :ts_style_set_tip_color,
    :ts_style_set_branch_color, :ts_style_set_branch_width, :ts_style_set_scale_bar,
    :ts_style_set_support_labels,
    :ts_viridis, :ts_default_palette, :ts_value_range, :ts_continuous_tip_t,
    :ts_continuous_branch_t, :ts_branch_widths, :ts_discrete_branch_codes,
    :ts_scene_options_default, :ts_circular_scene_options_default,
    :ts_render_rectangular_svg, :ts_render_circular_svg,
)
const _SYMBOLS = Ref{Dict{Symbol,Ptr{Cvoid}}}()

const _LIB_NAMES = ("libtreescape_jl_connector.so", "libtreescape_jl_connector.dylib", "treescape_jl_connector.dll")

"""
    library_path() -> String

Where the connector library is loaded from: `ENV["TREESCAPE_JL_LIB"]`,
then the `libpath` preference (see [`set_library!`](@ref)), then a
development build at `<repo>/target/release/` next to this package.
"""
function library_path()
    haskey(ENV, "TREESCAPE_JL_LIB") && return ENV["TREESCAPE_JL_LIB"]
    pref = @load_preference("libpath", nothing)
    pref !== nothing && return pref
    repo = normpath(joinpath(@__DIR__, "..", "..", ".."))
    for name in _LIB_NAMES
        candidate = joinpath(repo, "target", "release", name)
        isfile(candidate) && return candidate
    end
    error(
        "treescape connector library not found. Build it with " *
        "`cargo build -p treescape-jl-connector --release` in the treescape repository, " *
        "or point ENV[\"TREESCAPE_JL_LIB\"] / Treescape.set_library!(path) at it.",
    )
end

"""
    set_library!(path)

Persist the connector library location as a Preferences.jl preference.
Takes effect in new Julia sessions.
"""
set_library!(path::AbstractString) = @set_preferences!("libpath" => abspath(path))

function _load!()
    lock(_LOCK) do
        _HANDLE[] != C_NULL && return nothing
        path = library_path()
        handle = Libdl.dlopen(path)
        try
            version = ccall(Libdl.dlsym(handle, :ts_abi_version), UInt32, ())
            version == ABI_VERSION ||
                error("treescape connector at $path has ABI version $version; Treescape.jl needs $ABI_VERSION")
            _SYMBOLS[] = Dict(name => Libdl.dlsym(handle, name) for name in _SYMBOL_NAMES)
        catch
            # Not a (compatible) treescape library: release it before rethrowing.
            Libdl.dlclose(handle)
            rethrow()
        end
        # Publish the handle last: a non-null handle means the table is complete.
        _HANDLE[] = handle
    end
    return nothing
end

"""Function pointer for a `ts_*` symbol."""
function sym(name::Symbol)
    _HANDLE[] == C_NULL && _load!()
    return _SYMBOLS[][name]
end

"""Take ownership of a string returned by the library."""
function take_string!(p::Ptr{UInt8})
    p == C_NULL && return ""
    try
        return unsafe_string(p)
    finally
        ccall(sym(:ts_string_free), Cvoid, (Ptr{UInt8},), p)
    end
end

"""Throw for a non-zero status, consuming the error message."""
function check(status::Int32, err::Ref{Ptr{UInt8}})
    status == TS_OK && return nothing
    msg = take_string!(err[])
    isempty(msg) && (msg = "treescape error (status $status)")
    status == TS_INVALID_ARGUMENT && throw(ArgumentError(msg))
    throw(TreescapeError(status, msg))
end

# Mirrors of the `#[repr(C)]` option structs in treescape-jl-connector/src/render.rs.

struct SceneOptions
    px_per_x::Float64
    px_per_y::Float64
    padding::Float64
    font_size::Float64
    label_offset::Float64
    stroke_width::Float64
end

struct CircularSceneOptions
    px_per_r::Float64
    padding::Float64
    font_size::Float64
    label_offset::Float64
    stroke_width::Float64
    start_angle::Float64
    sweep_total::Float64
end

function default_scene_options()
    out = Ref{SceneOptions}()
    err = Ref{Ptr{UInt8}}(C_NULL)
    check(ccall(sym(:ts_scene_options_default), Int32, (Ptr{SceneOptions}, Ptr{Ptr{UInt8}}), out, err), err)
    return out[]
end

function default_circular_scene_options()
    out = Ref{CircularSceneOptions}()
    err = Ref{Ptr{UInt8}}(C_NULL)
    check(
        ccall(
            sym(:ts_circular_scene_options_default),
            Int32,
            (Ptr{CircularSceneOptions}, Ptr{Ptr{UInt8}}),
            out,
            err,
        ),
        err,
    )
    return out[]
end
