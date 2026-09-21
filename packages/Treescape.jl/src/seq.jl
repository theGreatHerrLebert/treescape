# Distances from aligned sequences (docs/conventions.md, "Distances from
# aligned sequences").

"""
    distances(source; model = :jc69, alphabet = :auto) -> (D::Matrix{Float64}, labels::Vector{String})

Pairwise distances between aligned sequences. `source` is FASTA text (a
string starting with `>`), the path of an aligned FASTA file, or a
collection of `label => sequence` pairs (a vector of pairs or a `Dict`).
Models: `:p`, `:jc69` (4 states for nucleotides, 20 for proteins), `:k2p`
(nucleotides), `:poisson` (proteins). Gaps and ambiguity codes are removed
pair by pair. The sequences must already be aligned. Same values and same
error text as Python's `treescape.distances` (error indices are 0-based).

`alphabet = :auto` treats sequences made only of nucleotide codes as
nucleotides. Short proteins can consist only of such letters; when that
looks likely, a warning (group `:treescape_sequence`) suggests
`alphabet = :protein`.

```julia
D, labels = distances("aligned.fasta"; model = :k2p)
p = TreePlot(D, labels; method = :nj)
```
"""
function distances(source; model::Symbol = :jc69, alphabet::Symbol = :auto)
    out = Ref{Ptr{Cvoid}}(C_NULL)
    err = Ref{Ptr{UInt8}}(C_NULL)
    if source isa AbstractString
        text = _is_fasta_text(source) ? String(source) : read(source, String)
        status = ccall(
            sym(:ts_seq_distances_from_fasta), Int32,
            (Cstring, Cstring, Cstring, Ptr{Ptr{Cvoid}}, Ptr{Ptr{UInt8}}),
            text, string(model), string(alphabet), out, err,
        )
    else
        pairs = collect(source)
        labels = String[string(first(p)) for p in pairs]
        seqs = String[string(last(p)) for p in pairs]
        status = GC.@preserve labels seqs ccall(
            sym(:ts_seq_distances_from_records), Int32,
            (Ptr{Cstring}, Ptr{Cstring}, Csize_t, Cstring, Cstring, Ptr{Ptr{Cvoid}}, Ptr{Ptr{UInt8}}),
            [Base.unsafe_convert(Cstring, Base.cconvert(Cstring, s)) for s in labels],
            [Base.unsafe_convert(Cstring, Base.cconvert(Cstring, s)) for s in seqs],
            length(pairs), string(model), string(alphabet), out, err,
        )
    end
    check(status, err)
    return _take_distances!(out[])
end

_is_fasta_text(s::AbstractString) = startswith(lstrip(c -> c in (' ', '\t', '\r', '\v', '\f', '\n'), s), '>')

function _take_distances!(handle::Ptr{Cvoid})
    try
        e = Ref{Ptr{UInt8}}(C_NULL)
        n = Ref{Csize_t}(0)
        check(ccall(sym(:ts_distances_n), Int32, (Ptr{Cvoid}, Ptr{Csize_t}, Ptr{Ptr{UInt8}}), handle, n, e), e)
        k = Int(n[])
        flat = Vector{Float64}(undef, k * k)
        check(ccall(sym(:ts_distances_copy), Int32, (Ptr{Cvoid}, Ptr{Float64}, Csize_t, Ptr{Ptr{UInt8}}), handle, flat, length(flat), e), e)
        labels = String[]
        for i in 0:(k - 1)
            s = Ref{Ptr{UInt8}}(C_NULL)
            check(ccall(sym(:ts_distances_label), Int32, (Ptr{Cvoid}, Csize_t, Ptr{Ptr{UInt8}}, Ptr{Ptr{UInt8}}), handle, i, s, e), e)
            push!(labels, take_string!(s[]))
        end
        doubtful = Ref{UInt8}(0)
        check(ccall(sym(:ts_distances_doubtful), Int32, (Ptr{Cvoid}, Ptr{UInt8}, Ptr{Ptr{UInt8}}), handle, doubtful, e), e)
        if doubtful[] == 0x01
            @warn "alphabet = :auto treated these sequences as nucleotides, but most of their letters are nucleotide ambiguity codes; if they are proteins, pass alphabet = :protein" _group = :treescape_sequence
        end
        # Row-major from the C side: transpose so D[i, j] is row i, column j.
        return (permutedims(reshape(flat, k, k)), labels)
    finally
        ccall(sym(:ts_distances_free), Cvoid, (Ptr{Cvoid},), handle)
    end
end
