# Runner for claim treescape-jl-ffi-no-abort.
#
#   julia --project=packages/Treescape.jl packages/Treescape.jl/test/ffi_no_abort.jl
#
# Drives every ts_* entry point with hostile input through raw ccall.
# The connector's release profile uses panic = "abort", so a panic kills
# this process: tests/oracle/test_jl_ffi_no_abort.py then reports the last
# `CASE` line printed. Each case checks its status code (exact where the
# contract fixes one, else "any status, process survives") and that every
# non-zero status carries a message. Prints `DONE <cases> <failures>` last.

using Random
using Treescape

const sym = Treescape.sym
const ERR = Ptr{Ptr{UInt8}}
const ANY_STATUS = 0:4

n_cases = 0
failures = String[]

function case(f, name, expected)
    global n_cases += 1
    println("CASE ", name)
    flush(stdout)
    err = Ref{Ptr{UInt8}}(C_NULL)
    status = Int(f(err))
    msg = err[] == C_NULL ? "" : Treescape.take_string!(err[])
    status in expected || push!(failures, "$name: status $status, expected $expected ($msg)")
    status != 0 && isempty(msg) && push!(failures, "$name: status $status without a message")
    return status
end

# --- helpers ----------------------------------------------------------------

function parse_tree(newick, err=Ref{Ptr{UInt8}}(C_NULL))
    out = Ref{Ptr{Cvoid}}(C_NULL)
    status = ccall(sym(:ts_tree_parse_newick), Int32, (Cstring, Ptr{Ptr{Cvoid}}, ERR), newick, out, err)
    return status, out[]
end

free_tree(t) = ccall(sym(:ts_tree_free), Cvoid, (Ptr{Cvoid},), t)

function render(tree, fn, opts, style, err)
    out = Ref{Ptr{UInt8}}(C_NULL)
    status = ccall(sym(fn), Int32, (Ptr{Cvoid}, Ptr{Cvoid}, Ptr{Cvoid}, Ptr{Ptr{UInt8}}, ERR), tree, opts, style, out, err)
    out[] == C_NULL || Treescape.take_string!(out[])
    return status
end

const VALID = "((a:0.1,b:0.2)95:0.3,(c:0.15,(d:0.05,e:0.07)70:0.1)88:0.2);"
const INVALID_UTF8 = UInt8[0x28, 0xff, 0xfe, 0x3b, 0x00]

# --- tree -------------------------------------------------------------------

out_tree = Ref{Ptr{Cvoid}}(C_NULL)
case("parse null src", [1]) do err
    ccall(sym(:ts_tree_parse_newick), Int32, (Ptr{UInt8}, Ptr{Ptr{Cvoid}}, ERR), C_NULL, out_tree, err)
end
case("parse invalid utf8", [1]) do err
    GC.@preserve INVALID_UTF8 ccall(
        sym(:ts_tree_parse_newick), Int32, (Ptr{UInt8}, Ptr{Ptr{Cvoid}}, ERR), pointer(INVALID_UTF8), out_tree, err,
    )
end
case("parse null out", [1]) do err
    ccall(sym(:ts_tree_parse_newick), Int32, (Cstring, Ptr{Cvoid}, ERR), VALID, C_NULL, err)
end
for bad in ("", ";", "(", ")", "((a,b);", "(a,b));", "(a:x,b);", "(a,b)", "(,);", "(a:1e999,b:-1e999);", "'unterminated;")
    case("parse $(repr(bad))", ANY_STATUS) do err
        status, t = parse_tree(bad, err)
        t == C_NULL || free_tree(t)
        status
    end
end

# v0.5 fuzz finding: a stray ']' used to loop forever until OOM.
for bad in ("a];", "(a,b)];", "8\"312XZXE6-; E7E()X]9c-\" 5\n")
    case("parse stray bracket $(repr(bad))", [2]) do err
        status, t = parse_tree(bad, err)
        t == C_NULL || free_tree(t)
        status
    end
end

status, tree = parse_tree(VALID)
@assert status == 0
n_nodes = Ref{Csize_t}(0)
ccall(sym(:ts_tree_n_nodes), Int32, (Ptr{Cvoid}, Ptr{Csize_t}, ERR), tree, n_nodes, C_NULL)
const N = Int(n_nodes[])

for fn in (:ts_tree_n_nodes, :ts_tree_n_tips, :ts_tree_root)
    case("$fn null tree", [1]) do err
        ccall(sym(fn), Int32, (Ptr{Cvoid}, Ptr{Csize_t}, ERR), C_NULL, Ref{Csize_t}(0), err)
    end
    case("$fn null out", [1]) do err
        ccall(sym(fn), Int32, (Ptr{Cvoid}, Ptr{Csize_t}, ERR), tree, C_NULL, err)
    end
end
for id in (N, N + 1, typemax(Csize_t))
    case("is_tip id $id", [1]) do err
        ccall(sym(:ts_tree_is_tip), Int32, (Ptr{Cvoid}, Csize_t, Ptr{UInt8}, ERR), tree, id, Ref{UInt8}(0), err)
    end
    case("node_name id $id", [1]) do err
        ccall(sym(:ts_tree_node_name), Int32, (Ptr{Cvoid}, Csize_t, Ptr{Ptr{UInt8}}, ERR), tree, id, Ref{Ptr{UInt8}}(C_NULL), err)
    end
    case("tip_name index $id", [1]) do err
        ccall(sym(:ts_tree_tip_name), Int32, (Ptr{Cvoid}, Csize_t, Ptr{Ptr{UInt8}}, ERR), tree, id, Ref{Ptr{UInt8}}(C_NULL), err)
    end
end
case("preorder small buffer", [1]) do err
    buf = zeros(Csize_t, 2)
    ccall(sym(:ts_tree_preorder), Int32, (Ptr{Cvoid}, Ptr{Csize_t}, Csize_t, Ptr{Csize_t}, ERR), tree, buf, 2, Ref{Csize_t}(0), err)
end
case("preorder null buffer", [1]) do err
    ccall(sym(:ts_tree_preorder), Int32, (Ptr{Cvoid}, Ptr{Csize_t}, Csize_t, Ptr{Csize_t}, ERR), tree, C_NULL, N, Ref{Csize_t}(0), err)
end
case("free null handles", [0]) do err
    ccall(sym(:ts_tree_free), Cvoid, (Ptr{Cvoid},), C_NULL)
    ccall(sym(:ts_style_free), Cvoid, (Ptr{Cvoid},), C_NULL)
    ccall(sym(:ts_string_free), Cvoid, (Ptr{UInt8},), C_NULL)
    Int32(0)
end

# --- style builder ----------------------------------------------------------

function with_style(f)
    style = ccall(sym(:ts_style_new), Ptr{Cvoid}, ())
    try
        return f(style)
    finally
        ccall(sym(:ts_style_free), Cvoid, (Ptr{Cvoid},), style)
    end
end

case("highlight null style", [1]) do err
    ccall(sym(:ts_style_add_highlight), Int32, (Ptr{Cvoid}, Ptr{Cstring}, Csize_t, UInt8, UInt8, UInt8, UInt8, ERR), C_NULL, C_NULL, 0, 0, 0, 0, 0, err)
end
case("highlight null names", [1]) do err
    with_style(s -> ccall(sym(:ts_style_add_highlight), Int32, (Ptr{Cvoid}, Ptr{Cstring}, Csize_t, UInt8, UInt8, UInt8, UInt8, ERR), s, C_NULL, 3, 0, 0, 0, 0, err))
end
case("highlight null name entry", [1]) do err
    names = [Ptr{UInt8}(C_NULL)]
    with_style(s -> ccall(sym(:ts_style_add_highlight), Int32, (Ptr{Cvoid}, Ptr{Ptr{UInt8}}, Csize_t, UInt8, UInt8, UInt8, UInt8, ERR), s, names, 1, 0, 0, 0, 0, err))
end
case("highlight invalid utf8 name", [1]) do err
    GC.@preserve INVALID_UTF8 begin
        names = [pointer(INVALID_UTF8)]
        with_style(s -> ccall(sym(:ts_style_add_highlight), Int32, (Ptr{Cvoid}, Ptr{Ptr{UInt8}}, Csize_t, UInt8, UInt8, UInt8, UInt8, ERR), s, names, 1, 0, 0, 0, 0, err))
    end
end
case("tip color null name", [1]) do err
    with_style(s -> ccall(sym(:ts_style_set_tip_color), Int32, (Ptr{Cvoid}, Ptr{UInt8}, UInt8, UInt8, UInt8, UInt8, ERR), s, C_NULL, 0, 0, 0, 0, err))
end
case("scale bar null label", [1]) do err
    with_style(s -> ccall(sym(:ts_style_set_scale_bar), Int32, (Ptr{Cvoid}, Float64, Ptr{UInt8}, ERR), s, 1.0, C_NULL, err))
end
for fn in (:ts_style_set_branch_color,)
    case("$fn null style", [1]) do err
        ccall(sym(fn), Int32, (Ptr{Cvoid}, Csize_t, UInt8, UInt8, UInt8, UInt8, ERR), C_NULL, 0, 0, 0, 0, 0, err)
    end
end
case("branch width null style", [1]) do err
    ccall(sym(:ts_style_set_branch_width), Int32, (Ptr{Cvoid}, Csize_t, Float64, ERR), C_NULL, 0, 1.0, err)
end
case("support labels null style", [1]) do err
    ccall(sym(:ts_style_set_support_labels), Int32, (Ptr{Cvoid}, UInt8, Float64, ERR), C_NULL, 0, 0.0, err)
end

# --- resolvers --------------------------------------------------------------

case("viridis NaN", [3]) do err
    ccall(sym(:ts_viridis), Int32, (Float64, Ptr{UInt8}, ERR), NaN, zeros(UInt8, 4), err)
end
case("viridis null out", [1]) do err
    ccall(sym(:ts_viridis), Int32, (Float64, Ptr{UInt8}, ERR), 0.5, C_NULL, err)
end
case("default palette exhausted", [3]) do err
    ccall(sym(:ts_default_palette), Int32, (Csize_t, Ptr{UInt8}, ERR), 11, zeros(UInt8, 44), err)
end
case("default palette null out", [1]) do err
    ccall(sym(:ts_default_palette), Int32, (Csize_t, Ptr{UInt8}, ERR), 3, C_NULL, err)
end
case("value range null values", [1]) do err
    ccall(sym(:ts_value_range), Int32, (Ptr{Float64}, Ptr{UInt8}, Csize_t, UInt8, Float64, UInt8, Float64, Ptr{Float64}, Ptr{Float64}, ERR),
        C_NULL, C_NULL, 5, 0, 0.0, 0, 0.0, Ref(0.0), Ref(0.0), err)
end
for (label, len) in (("short", 2), ("empty", 0), ("long", 9))
    vals = fill(0.5, len)
    present = ones(UInt8, len)
    case("continuous tip t $label column", [1]) do err
        ccall(sym(:ts_continuous_tip_t), Int32, (Ptr{Cvoid}, Ptr{Float64}, Ptr{UInt8}, Csize_t, Float64, Float64, Ptr{Float64}, Ptr{UInt8}, ERR),
            tree, vals, present, len, 0.0, 1.0, zeros(max(len, 1)), zeros(UInt8, max(len, 1)), err)
    end
    case("continuous branch t $label column", [1]) do err
        ccall(sym(:ts_continuous_branch_t), Int32, (Ptr{Cvoid}, Ptr{Float64}, Ptr{UInt8}, Csize_t, Float64, Float64, Ptr{Float64}, Ptr{UInt8}, ERR),
            tree, vals, present, len, 0.0, 1.0, zeros(N), zeros(UInt8, N), err)
    end
    case("branch widths $label column", [1]) do err
        ccall(sym(:ts_branch_widths), Int32, (Ptr{Cvoid}, Ptr{Float64}, Ptr{UInt8}, Csize_t, Float64, Float64, Float64, Float64, Ptr{Float64}, Ptr{UInt8}, ERR),
            tree, vals, present, len, 0.0, 1.0, 1.0, 4.0, zeros(N), zeros(UInt8, N), err)
    end
    case("discrete codes $label column", [1]) do err
        ccall(sym(:ts_discrete_branch_codes), Int32, (Ptr{Cvoid}, Ptr{UInt32}, Ptr{UInt8}, Csize_t, Ptr{UInt32}, Ptr{UInt8}, ERR),
            tree, zeros(UInt32, len), present, len, zeros(UInt32, N), zeros(UInt8, N), err)
    end
end
case("continuous branch t null tree", [1]) do err
    ccall(sym(:ts_continuous_branch_t), Int32, (Ptr{Cvoid}, Ptr{Float64}, Ptr{UInt8}, Csize_t, Float64, Float64, Ptr{Float64}, Ptr{UInt8}, ERR),
        C_NULL, zeros(5), ones(UInt8, 5), 5, 0.0, 1.0, zeros(N), zeros(UInt8, N), err)
end
case("continuous branch t null out", [1]) do err
    ccall(sym(:ts_continuous_branch_t), Int32, (Ptr{Cvoid}, Ptr{Float64}, Ptr{UInt8}, Csize_t, Float64, Float64, Ptr{Float64}, Ptr{UInt8}, ERR),
        tree, zeros(5), ones(UInt8, 5), 5, 0.0, 1.0, C_NULL, C_NULL, err)
end
for special in (NaN, Inf, -Inf)
    case("branch widths value $special", ANY_STATUS) do err
        ccall(sym(:ts_branch_widths), Int32, (Ptr{Cvoid}, Ptr{Float64}, Ptr{UInt8}, Csize_t, Float64, Float64, Float64, Float64, Ptr{Float64}, Ptr{UInt8}, ERR),
            tree, [special, 0.1, 0.2, 0.3, 0.4], ones(UInt8, 5), 5, special, 1.0, 1.0, special, zeros(N), zeros(UInt8, N), err)
    end
end

# --- render -----------------------------------------------------------------

for fn in (:ts_render_rectangular_svg, :ts_render_circular_svg)
    case("$fn null tree", [1]) do err
        render(C_NULL, fn, C_NULL, C_NULL, err)
    end
    case("$fn null out", [1]) do err
        ccall(sym(fn), Int32, (Ptr{Cvoid}, Ptr{Cvoid}, Ptr{Cvoid}, Ptr{Cvoid}, ERR), tree, C_NULL, C_NULL, C_NULL, err)
    end
    case("$fn branch id out of range", [1]) do err
        with_style() do s
            ccall(sym(:ts_style_set_branch_color), Int32, (Ptr{Cvoid}, Csize_t, UInt8, UInt8, UInt8, UInt8, ERR), s, N + 7, 1, 2, 3, 4, C_NULL)
            render(tree, fn, C_NULL, s, err)
        end
    end
    case("$fn whole-tree highlight", fn === :ts_render_circular_svg ? [4] : ANY_STATUS) do err
        with_style() do s
            names = ["a", "b", "c", "d", "e"]
            GC.@preserve names begin
                ptrs = [pointer(n) for n in names]
                ccall(sym(:ts_style_add_highlight), Int32, (Ptr{Cvoid}, Ptr{Ptr{UInt8}}, Csize_t, UInt8, UInt8, UInt8, UInt8, ERR), s, ptrs, 5, 1, 2, 3, 4, C_NULL)
            end
            render(tree, fn, C_NULL, s, err)
        end
    end
    case("$fn unknown highlight tips", ANY_STATUS) do err
        with_style() do s
            names = ["nope", "a"]
            GC.@preserve names begin
                ptrs = [pointer(n) for n in names]
                ccall(sym(:ts_style_add_highlight), Int32, (Ptr{Cvoid}, Ptr{Ptr{UInt8}}, Csize_t, UInt8, UInt8, UInt8, UInt8, ERR), s, ptrs, 2, 1, 2, 3, 4, C_NULL)
            end
            render(tree, fn, C_NULL, s, err)
        end
    end
    for special in (NaN, Inf, -Inf, -5.0, 0.0)
        case("$fn options $special", ANY_STATUS) do err
            opts = fn === :ts_render_rectangular_svg ?
                Ref(Treescape.SceneOptions(special, special, special, special, special, special)) :
                Ref(Treescape.CircularSceneOptions(special, special, special, special, special, special, special))
            render(tree, fn, Base.unsafe_convert(Ptr{Cvoid}, opts), C_NULL, err)
        end
        case("$fn styled specials $special", ANY_STATUS) do err
            with_style() do s
                ccall(sym(:ts_style_set_branch_width), Int32, (Ptr{Cvoid}, Csize_t, Float64, ERR), s, 1, special, C_NULL)
                ccall(sym(:ts_style_set_scale_bar), Int32, (Ptr{Cvoid}, Float64, Cstring, ERR), s, special, "bar", C_NULL)
                ccall(sym(:ts_style_set_support_labels), Int32, (Ptr{Cvoid}, UInt8, Float64, ERR), s, 1, special, C_NULL)
                render(tree, fn, C_NULL, s, err)
            end
        end
    end
end

# --- seeded fuzz: random strings and mutations of a valid tree --------------

const ALPHABET = collect("():,;[]'\" \t\nabcXYZ0123456789.-+eE_&=\\")
rng = MersenneTwister(20260921)

function fuzz_case(name, text)
    case(name, ANY_STATUS) do err
        status, t = parse_tree(text, err)
        if status == 0
            # Exercise layout + render on whatever parsed.
            for fn in (:ts_render_rectangular_svg, :ts_render_circular_svg)
                e = Ref{Ptr{UInt8}}(C_NULL)
                render(t, fn, C_NULL, C_NULL, e)
                e[] == C_NULL || Treescape.take_string!(e[])
            end
            free_tree(t)
        end
        status
    end
end

for i in 1:500
    fuzz_case("random $i", String(rand(rng, ALPHABET, rand(rng, 0:40))))
end
for i in 1:1000
    chars = collect(VALID)
    for _ in 1:rand(rng, 1:4)
        k = rand(rng, 1:length(chars))
        r = rand(rng)
        if r < 0.33
            deleteat!(chars, k)
        elseif r < 0.66
            insert!(chars, k, rand(rng, ALPHABET))
        else
            chars[k] = rand(rng, ALPHABET)
        end
        isempty(chars) && break
    end
    fuzz_case("mutation $i", String(chars))
end

free_tree(tree)

for f in failures
    println("FAIL ", f)
end
println("DONE ", n_cases, " ", length(failures))
