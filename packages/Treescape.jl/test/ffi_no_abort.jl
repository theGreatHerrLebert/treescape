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

# Review round 2: large inputs. Over the byte limit is rejected before
# parsing; the worst case at the limit (every byte opens a node) must
# end in a status, never an allocation-failure abort, under the
# runner's address-space cap.
const LIMIT = 16 * 1024 * 1024
case("parse over the size limit", [1]) do err
    status, t = parse_tree("a"^LIMIT * ";", err)
    t == C_NULL || free_tree(t)
    status
end
case("parse worst case at the size limit", ANY_STATUS) do err
    status, t = parse_tree("("^LIMIT, err)
    t == C_NULL || free_tree(t)
    status
end

# Oversized buffer: a length whose byte size overflows isize.
case("value_range oversized length", [1]) do err
    v, pr = [0.5, 0.5], UInt8[1, 1]
    ccall(
        sym(:ts_value_range), Int32,
        (Ptr{Float64}, Ptr{UInt8}, Csize_t, UInt8, Float64, UInt8, Float64, Ptr{Float64}, Ptr{Float64}, ERR),
        v, pr, typemax(Csize_t) ÷ 2, 0, 0.0, 0, 0.0, Ref(0.0), Ref(0.0), err,
    )
end

# v0.6: trees from distance matrices.
const D3 = [0.0, 1.0, 2.0, 1.0, 0.0, 1.5, 2.0, 1.5, 0.0]
const L3 = ["a", "b", "c"]
function from_distances(matrix, n, labels, method, err)
    out = Ref{Ptr{Cvoid}}(C_NULL)
    status = GC.@preserve labels ccall(sym(:ts_tree_from_distances), Int32,
        (Ptr{Float64}, Csize_t, Ptr{Ptr{UInt8}}, UInt32, Ptr{Ptr{Cvoid}}, Ptr{Ptr{UInt8}}), matrix, n,
        labels === nothing ? C_NULL : [pointer(l) for l in labels], method, out, err)
    out[] == C_NULL || free_tree(out[])
    status
end
case("distances valid", [0]) do err
    from_distances(D3, 3, L3, 0, err)
end
case("distances null matrix", [1]) do err
    from_distances(C_NULL, 3, L3, 0, err)
end
case("distances null labels", [1]) do err
    from_distances(D3, 3, nothing, 1, err)
end
case("distances over the taxa limit", [1]) do err
    from_distances(D3, 10_001, L3, 0, err)
end
case("distances n*n overflows", [1]) do err
    from_distances(D3, typemax(Csize_t), L3, 0, err)
end
case("distances bad method", [1]) do err
    from_distances(D3, 3, L3, 7, err)
end
case("distances NaN entry", [1]) do err
    from_distances([0.0, NaN, 2.0, NaN, 0.0, 1.5, 2.0, 1.5, 0.0], 3, L3, 0, err)
end
case("distances n = 1", [1]) do err
    from_distances([0.0], 1, ["a"], 1, err)
end
case("linkage null", [1]) do err
    out = Ref{Ptr{Cvoid}}(C_NULL)
    GC.@preserve L3 ccall(sym(:ts_tree_from_linkage), Int32, (Ptr{Float64}, Csize_t, Ptr{Ptr{UInt8}}, Ptr{Ptr{Cvoid}}, ERR),
        C_NULL, 3, [pointer(l) for l in L3], out, err)
end
case("linkage cluster out of range", [1]) do err
    out = Ref{Ptr{Cvoid}}(C_NULL)
    GC.@preserve L3 ccall(sym(:ts_tree_from_linkage), Int32, (Ptr{Float64}, Csize_t, Ptr{Ptr{UInt8}}, Ptr{Ptr{Cvoid}}, ERR),
        [0.0, 9.0, 1.0, 2.0, 2.0, 3.0, 2.0, 3.0], 3, [pointer(l) for l in L3], out, err)
end

# v0.7: distances from aligned sequences.
function seq_distances(text, model, alphabet, err)
    out = Ref{Ptr{Cvoid}}(C_NULL)
    status = ccall(sym(:ts_seq_distances_from_fasta), Int32, (Ptr{UInt8}, Ptr{UInt8}, Ptr{UInt8}, Ptr{Ptr{Cvoid}}, Ptr{Ptr{UInt8}}),
        text === nothing ? C_NULL : pointer(text), model === nothing ? C_NULL : pointer(model),
        alphabet === nothing ? C_NULL : pointer(alphabet), out, err)
    out[] == C_NULL || ccall(sym(:ts_distances_free), Cvoid, (Ptr{Cvoid},), out[])
    status
end
const FASTA_OK = ">a\nACGT\n>b\nACGA\n\0"
for (name, text, model, alphabet, expected) in (
    ("seq valid", FASTA_OK, "jc69\0", "auto\0", [0]),
    ("seq null text", nothing, "jc69\0", "auto\0", [1]),
    ("seq null model", FASTA_OK, nothing, "auto\0", [1]),
    ("seq null alphabet", FASTA_OK, "jc69\0", nothing, [1]),
    ("seq bad model", FASTA_OK, "gtr\0", "auto\0", [1]),
    ("seq bad alphabet", FASTA_OK, "p\0", "rna\0", [1]),
    ("seq unaligned", ">a\nACGT\n>b\nACG\n\0", "p\0", "auto\0", [1]),
    ("seq no header", "ACGT\n\0", "p\0", "auto\0", [1]),
    ("seq one sequence", ">a\nACGT\n\0", "p\0", "auto\0", [1]),
    ("seq saturated", ">a\nAAAA\n>b\nCCCC\n\0", "jc69\0", "auto\0", [1]),
    ("seq invalid utf8", ">a\nAC\xffT\n>b\nACGA\n\0", "p\0", "auto\0", [1]),
)
    case(name, expected) do err
        GC.@preserve text model alphabet seq_distances(text === nothing ? nothing : Vector{UInt8}(text),
            model === nothing ? nothing : Vector{UInt8}(model), alphabet === nothing ? nothing : Vector{UInt8}(alphabet), err)
    end
end
case("distances accessors on null", [1]) do err
    ccall(sym(:ts_distances_n), Int32, (Ptr{Cvoid}, Ptr{Csize_t}, ERR), C_NULL, Ref{Csize_t}(0), err)
end
case("distances doubtful on null", [1]) do err
    ccall(sym(:ts_distances_doubtful), Int32, (Ptr{Cvoid}, Ptr{UInt8}, ERR), C_NULL, Ref{UInt8}(0), err)
end
function seq_records(labels, seqs, n, model, alphabet, err)
    out = Ref{Ptr{Cvoid}}(C_NULL)
    lp = labels === nothing ? C_NULL : [l === nothing ? C_NULL : pointer(l) for l in labels]
    sp = seqs === nothing ? C_NULL : [s === nothing ? C_NULL : pointer(s) for s in seqs]
    status = GC.@preserve labels seqs lp sp ccall(sym(:ts_seq_distances_from_records), Int32,
        (Ptr{Ptr{UInt8}}, Ptr{Ptr{UInt8}}, Csize_t, Ptr{UInt8}, Ptr{UInt8}, Ptr{Ptr{Cvoid}}, Ptr{Ptr{UInt8}}),
        lp, sp, n, model, alphabet, out, err)
    if out[] != C_NULL
        flag = Ref{UInt8}(2)
        @assert ccall(sym(:ts_distances_doubtful), Int32, (Ptr{Cvoid}, Ptr{UInt8}, ERR), out[], flag, C_NULL) == 0
        @assert flag[] in (0, 1)
        ccall(sym(:ts_distances_free), Cvoid, (Ptr{Cvoid},), out[])
    end
    status
end
const REC_L = ["a\0", "b c\0"]
const REC_S = ["ACGT\0", "ACGA\0"]
for (name, labels, seqs, n, model, alphabet, expected) in (
    ("records valid", REC_L, REC_S, 2, "p\0", "auto\0", [0]),
    ("records doubtful", REC_L, ["MKWRAC\0", "MKWRAG\0"], 2, "p\0", "auto\0", [0]),
    ("records null labels", nothing, REC_S, 2, "p\0", "auto\0", [1]),
    ("records null seqs", REC_L, nothing, 2, "p\0", "auto\0", [1]),
    ("records null label entry", ["a\0", nothing], REC_S, 2, "p\0", "auto\0", [1]),
    ("records null sequence entry", REC_L, ["ACGT\0", nothing], 2, "p\0", "auto\0", [1]),
    ("records n zero", REC_L, REC_S, 0, "p\0", "auto\0", [1]),
    ("records n over limit", REC_L, REC_S, 10_001, "p\0", "auto\0", [1]),
    ("records duplicate label", ["a\0", "a\0"], REC_S, 2, "p\0", "auto\0", [1]),
    ("records bad alphabet", REC_L, REC_S, 2, "p\0", "dna\0", [1]),
    ("records null model", REC_L, REC_S, 2, nothing, "auto\0", [1]),
    ("records invalid utf8", REC_L, ["AC\xffT\0", "ACGA\0"], 2, "p\0", "auto\0", [1]),
)
    case(name, expected) do err
        lb = labels === nothing ? nothing : [l === nothing ? nothing : Vector{UInt8}(l) for l in labels]
        sb = seqs === nothing ? nothing : [s === nothing ? nothing : Vector{UInt8}(s) for s in seqs]
        m = model === nothing ? C_NULL : Vector{UInt8}(model)
        a = Vector{UInt8}(alphabet)
        GC.@preserve m a seq_records(lb, sb, n, m === C_NULL ? C_NULL : pointer(m), pointer(a), err)
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
    case("$fn misaligned options", [1]) do err
        buf = zeros(UInt8, 128)
        GC.@preserve buf render(tree, fn, pointer(buf) + 1, C_NULL, err)
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
    fn === :ts_render_rectangular_svg && for code in (UInt32(4), typemax(UInt32))
        case("$fn orientation code $code", [1]) do err
            opts = Ref(Treescape.SceneOptions(60.0, 18.0, 12.0, 12.0, 4.0, 1.0, code))
            render(tree, fn, Base.unsafe_convert(Ptr{Cvoid}, opts), C_NULL, err)
        end
    end
    for special in (NaN, Inf, -Inf, -5.0, 0.0)
        case("$fn options $special", ANY_STATUS) do err
            opts = fn === :ts_render_rectangular_svg ?
                Ref(Treescape.SceneOptions(special, special, special, special, special, special, UInt32(1))) :
                Ref(Treescape.CircularSceneOptions(special, special, special, special, special, special, special))
            render(tree, fn, Base.unsafe_convert(Ptr{Cvoid}, opts), C_NULL, err)
        end
        fn === :ts_render_rectangular_svg && for code in UInt32[0, 2, 3]
            case("$fn orientation $code options $special", ANY_STATUS) do err
                opts = Ref(Treescape.SceneOptions(special, special, special, special, special, special, code))
                render(tree, fn, Base.unsafe_convert(Ptr{Cvoid}, opts), C_NULL, err)
            end
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
