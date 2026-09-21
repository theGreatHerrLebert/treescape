//! PyO3 bindings for `treescape_core::style` — metadata-driven styling
//! resolution (v0.5 Phase 1). Signatures mirror
//! `treescape_reference.style` so `plot.py` and the parity tests can
//! swap one for the other.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use treescape_core::style::{self as core_style, Rgba, StyleError};
use treescape_core::tree::NodeId;

use crate::py_tree::PyTree;

fn to_py_err(e: StyleError) -> PyErr {
    PyValueError::new_err(e.to_string())
}

#[pyfunction]
fn viridis(t: f64) -> PyResult<Rgba> {
    core_style::viridis(t).map_err(to_py_err)
}

#[pyfunction]
fn default_palette(n_values: usize) -> PyResult<Vec<&'static str>> {
    core_style::default_palette(n_values).map_err(to_py_err)
}

#[pyfunction]
fn neumaier_sum(values: Vec<f64>) -> f64 {
    core_style::neumaier_sum(&values)
}

#[pyfunction]
#[pyo3(signature = (tip_values, vmin, vmax))]
fn value_range(tip_values: Vec<Option<f64>>, vmin: Option<f64>, vmax: Option<f64>) -> (f64, f64) {
    core_style::value_range(&tip_values, vmin, vmax)
}

#[pyfunction]
fn normalize(value: f64, lo: f64, hi: f64) -> f64 {
    core_style::normalize(value, lo, hi)
}

#[pyfunction]
fn descendant_tips(tree: &PyTree, node_id: NodeId) -> PyResult<Vec<NodeId>> {
    if node_id >= tree.inner.len() {
        return Err(PyValueError::new_err(format!(
            "node id {node_id} out of range"
        )));
    }
    Ok(core_style::descendant_tips(&tree.inner, node_id))
}

#[pyfunction]
fn continuous_tip_t(
    tree: &PyTree,
    tip_values: Vec<Option<f64>>,
    lo: f64,
    hi: f64,
) -> PyResult<Vec<(String, f64)>> {
    core_style::continuous_tip_t(&tree.inner, &tip_values, lo, hi).map_err(to_py_err)
}

#[pyfunction]
fn continuous_branch_t(
    tree: &PyTree,
    tip_values: Vec<Option<f64>>,
    lo: f64,
    hi: f64,
) -> PyResult<Vec<(NodeId, f64)>> {
    core_style::continuous_branch_t(&tree.inner, &tip_values, lo, hi).map_err(to_py_err)
}

#[pyfunction]
fn branch_widths(
    tree: &PyTree,
    tip_values: Vec<Option<f64>>,
    lo: f64,
    hi: f64,
    wmin: f64,
    wmax: f64,
) -> PyResult<Vec<(NodeId, f64)>> {
    core_style::branch_widths(&tree.inner, &tip_values, lo, hi, wmin, wmax).map_err(to_py_err)
}

/// `(colored, non_monophyletic)`: `[(node_id, code)]` and `[node_id]`,
/// both in preorder.
type DiscreteBranchCodes = (Vec<(NodeId, u32)>, Vec<NodeId>);

#[pyfunction]
fn discrete_branch_codes(
    tree: &PyTree,
    tip_codes: Vec<Option<u32>>,
) -> PyResult<DiscreteBranchCodes> {
    let res = core_style::discrete_branch_codes(&tree.inner, &tip_codes).map_err(to_py_err)?;
    Ok((res.colored, res.non_monophyletic))
}

#[pymodule]
pub fn py_style(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("TABLEAU_10", core_style::TABLEAU_10.to_vec())?;
    m.add("VIRIDIS_LUT", core_style::VIRIDIS_LUT.to_vec())?;
    m.add_function(wrap_pyfunction!(viridis, m)?)?;
    m.add_function(wrap_pyfunction!(default_palette, m)?)?;
    m.add_function(wrap_pyfunction!(neumaier_sum, m)?)?;
    m.add_function(wrap_pyfunction!(value_range, m)?)?;
    m.add_function(wrap_pyfunction!(normalize, m)?)?;
    m.add_function(wrap_pyfunction!(descendant_tips, m)?)?;
    m.add_function(wrap_pyfunction!(continuous_tip_t, m)?)?;
    m.add_function(wrap_pyfunction!(continuous_branch_t, m)?)?;
    m.add_function(wrap_pyfunction!(branch_widths, m)?)?;
    m.add_function(wrap_pyfunction!(discrete_branch_codes, m)?)?;
    Ok(())
}
