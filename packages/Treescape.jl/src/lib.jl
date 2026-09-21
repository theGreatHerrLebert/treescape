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
const _SYMBOLS = Dict{Symbol,Ptr{Cvoid}}()
const _LOCK = ReentrantLock()

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

function _handle()
    _HANDLE[] != C_NULL && return _HANDLE[]
    lock(_LOCK) do
        _HANDLE[] != C_NULL && return _HANDLE[]
        path = library_path()
        handle = Libdl.dlopen(path)
        version = ccall(Libdl.dlsym(handle, :ts_abi_version), UInt32, ())
        if version != ABI_VERSION
            Libdl.dlclose(handle)
            error("treescape connector at $path has ABI version $version; Treescape.jl needs $ABI_VERSION")
        end
        _HANDLE[] = handle
    end
end

"""Function pointer for a `ts_*` symbol (cached)."""
function sym(name::Symbol)
    get(_SYMBOLS, name, C_NULL) != C_NULL && return _SYMBOLS[name]
    lock(_LOCK) do
        get!(() -> Libdl.dlsym(_handle(), name), _SYMBOLS, name)
    end
end

"""Take ownership of a string returned by the library."""
function take_string!(p::Ptr{UInt8})
    p == C_NULL && return ""
    s = unsafe_string(p)
    ccall(sym(:ts_string_free), Cvoid, (Ptr{UInt8},), p)
    return s
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
