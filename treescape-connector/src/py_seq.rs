//! PyO3 bindings for `treescape_core::seq_distance`.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use treescape_core::seq_distance;

fn to_py(e: seq_distance::SequenceError) -> PyErr {
    PyValueError::new_err(e.0)
}

/// `[(label, sequence)]` from FASTA text.
#[pyfunction]
fn read_fasta(text: &str) -> PyResult<Vec<(String, String)>> {
    seq_distance::read_fasta(text).map_err(to_py)
}

/// Row-major `n × n` distances (flat list), labels, and whether to warn
/// that auto-detection chose nucleotide for what looks like protein.
#[pyfunction]
#[pyo3(signature = (records, model = "jc69", alphabet = "auto"))]
fn distance_matrix(
    records: Vec<(String, String)>,
    model: &str,
    alphabet: &str,
) -> PyResult<(Vec<f64>, Vec<String>, bool)> {
    seq_distance::distance_matrix_checked(&records, model, alphabet).map_err(to_py)
}

/// `True` if `source` is FASTA text (starts with `>` after whitespace).
#[pyfunction]
fn is_fasta_text(source: &str) -> bool {
    seq_distance::is_fasta_text(source)
}

#[pymodule]
pub fn py_seq(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(read_fasta, m)?)?;
    m.add_function(wrap_pyfunction!(distance_matrix, m)?)?;
    m.add_function(wrap_pyfunction!(is_fasta_text, m)?)?;
    Ok(())
}
