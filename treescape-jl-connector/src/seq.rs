//! Distances from aligned sequences: compute, inspect, free.

use std::ffi::c_char;

use treescape_core::seq_distance;

use crate::ffi::{
    copy_out, finish, handle, slice_arg, str_arg, write_out, write_string, Failure, FfiResult,
};

/// Largest sequence input accepted (64 MiB, FASTA text or the sum of the
/// sequences). 10,000 sequences are also the tree builders' limit.
pub const MAX_FASTA_BYTES: usize = 64 * 1024 * 1024;
pub const MAX_SEQUENCES: usize = 10_000;

/// Opaque result: a row-major `n × n` matrix, its labels, and whether the
/// hosts should warn about auto-detection (docs/conventions.md).
pub struct TsDistances {
    matrix: Vec<f64>,
    labels: Vec<String>,
    doubtful: bool,
}

fn finish_distances(
    records: &[(String, String)],
    model: &str,
    alphabet: &str,
    out: *mut *mut TsDistances,
) -> FfiResult<()> {
    let (matrix, labels, doubtful) =
        seq_distance::distance_matrix_checked(records, model, alphabet)
            .map_err(|e| Failure::invalid(e.0))?;
    let boxed = Box::into_raw(Box::new(TsDistances {
        matrix,
        labels,
        doubtful,
    }));
    if let Err(f) = write_out(out, boxed, "out") {
        // SAFETY: `boxed` was just created and never shared.
        drop(unsafe { Box::from_raw(boxed) });
        return Err(f);
    }
    Ok(())
}

/// Distances between the aligned sequences in FASTA `text`. `model`:
/// `"p" | "jc69" | "k2p" | "poisson"`; `alphabet`: `"auto" | "nucleotide" |
/// "protein"` (docs/conventions.md, "Distances from aligned sequences").
/// Invalid input is status 1 with the reference's message.
#[no_mangle]
pub extern "C" fn ts_seq_distances_from_fasta(
    text: *const c_char,
    model: *const c_char,
    alphabet: *const c_char,
    out: *mut *mut TsDistances,
    err: *mut *mut c_char,
) -> i32 {
    let run = || -> FfiResult<()> {
        let text = str_arg(text, "text")?;
        if text.len() > MAX_FASTA_BYTES {
            return Err(Failure::invalid(format!(
                "FASTA input is {} bytes; the limit is {MAX_FASTA_BYTES}",
                text.len()
            )));
        }
        let model = str_arg(model, "model")?;
        let alphabet = str_arg(alphabet, "alphabet")?;
        // Count headers before building any record: 64 MiB of ">a\n" would
        // otherwise build ~22 million records first.
        let count = seq_distance::count_records(text);
        if count > MAX_SEQUENCES {
            return Err(Failure::invalid(format!(
                "{count} sequences; the limit is {MAX_SEQUENCES}"
            )));
        }
        let records = seq_distance::read_fasta(text).map_err(|e| Failure::invalid(e.0))?;
        finish_distances(&records, model, alphabet, out)
    };
    finish(run(), err)
}

/// Distances between `n` aligned sequences given as parallel arrays of
/// labels and sequences (no FASTA parsing, so labels may contain spaces).
/// Same models, alphabets and errors as `ts_seq_distances_from_fasta`.
#[no_mangle]
pub extern "C" fn ts_seq_distances_from_records(
    labels: *const *const c_char,
    seqs: *const *const c_char,
    n: usize,
    model: *const c_char,
    alphabet: *const c_char,
    out: *mut *mut TsDistances,
    err: *mut *mut c_char,
) -> i32 {
    let run = || -> FfiResult<()> {
        if n > MAX_SEQUENCES {
            return Err(Failure::invalid(format!(
                "{n} sequences; the limit is {MAX_SEQUENCES}"
            )));
        }
        let model = str_arg(model, "model")?;
        let alphabet = str_arg(alphabet, "alphabet")?;
        let labels = slice_arg(labels, n, "labels")?;
        let seqs = slice_arg(seqs, n, "seqs")?;
        let mut records = Vec::with_capacity(n);
        let mut bytes = 0usize;
        for (&l, &s) in labels.iter().zip(seqs) {
            let seq = str_arg(s, "sequence")?;
            bytes = bytes.saturating_add(seq.len());
            if bytes > MAX_FASTA_BYTES {
                return Err(Failure::invalid(format!(
                    "sequences exceed {MAX_FASTA_BYTES} bytes"
                )));
            }
            records.push((str_arg(l, "label")?.to_owned(), seq.to_owned()));
        }
        finish_distances(&records, model, alphabet, out)
    };
    finish(run(), err)
}

/// Number of sequences (the matrix is `n × n`).
#[no_mangle]
pub extern "C" fn ts_distances_n(
    d: *const TsDistances,
    out: *mut usize,
    err: *mut *mut c_char,
) -> i32 {
    let run = || write_out(out, handle(d, "distances")?.labels.len(), "out");
    finish(run(), err)
}

/// 1 if the hosts should warn that auto-detection chose nucleotide for
/// what looks like protein (docs/conventions.md), else 0.
#[no_mangle]
pub extern "C" fn ts_distances_doubtful(
    d: *const TsDistances,
    out: *mut u8,
    err: *mut *mut c_char,
) -> i32 {
    let run = || write_out(out, u8::from(handle(d, "distances")?.doubtful), "out");
    finish(run(), err)
}

/// Copy the row-major matrix into `buf` (at least `len = n²` elements).
#[no_mangle]
pub extern "C" fn ts_distances_copy(
    d: *const TsDistances,
    buf: *mut f64,
    len: usize,
    err: *mut *mut c_char,
) -> i32 {
    let run = || {
        let d = handle(d, "distances")?;
        if len < d.matrix.len() {
            return Err(Failure::invalid(format!(
                "buffer holds {len} values; the matrix has {}",
                d.matrix.len()
            )));
        }
        copy_out(buf, &d.matrix, "buf")
    };
    finish(run(), err)
}

/// Label `i` as an owned string (release with `ts_string_free`).
#[no_mangle]
pub extern "C" fn ts_distances_label(
    d: *const TsDistances,
    i: usize,
    out: *mut *mut c_char,
    err: *mut *mut c_char,
) -> i32 {
    let run = || {
        let d = handle(d, "distances")?;
        let label = d
            .labels
            .get(i)
            .ok_or_else(|| Failure::invalid(format!("label index {i} out of range")))?;
        write_string(out, label, "out")
    };
    finish(run(), err)
}

/// Release a result. Null is a no-op.
#[no_mangle]
pub extern "C" fn ts_distances_free(d: *mut TsDistances) {
    if !d.is_null() {
        // SAFETY: came from `Box::into_raw` in `ts_seq_distances_from_*`.
        drop(unsafe { Box::from_raw(d) });
    }
}
