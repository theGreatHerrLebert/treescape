//! PyO3 bindings for `treescape_core::style` — metadata-driven styling
//! resolution (v0.5 Phase 1). Signatures mirror
//! `treescape_reference.style` so `plot.py` and the parity tests can
//! swap one for the other.
//!
//! Integer arguments are taken as Python objects and range-checked here
//! so out-of-domain input raises the reference's `ValueError` /
//! `IndexError` rather than PyO3's generic `OverflowError`/`TypeError`.

use pyo3::exceptions::{PyIndexError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyInt};

use treescape_core::style::{self as core_style, Rgba, StyleError};
use treescape_core::tree::NodeId;

use crate::py_tree::PyTree;

fn to_py_err(e: StyleError) -> PyErr {
    PyValueError::new_err(e.to_string())
}

/// `Some(i64)` for a Python int (bool included, as `isinstance(x, int)`)
/// that fits, `None` for an int that does not; non-ints are `Err(())`.
fn as_int(obj: &Bound<'_, PyAny>) -> Result<Option<i64>, ()> {
    if obj.is_instance_of::<PyInt>() || obj.is_instance_of::<PyBool>() {
        Ok(obj.extract::<i64>().ok())
    } else {
        Err(())
    }
}

fn repr(obj: &Bound<'_, PyAny>) -> String {
    obj.repr()
        .map(|r| r.to_string())
        .unwrap_or_else(|_| "?".to_string())
}

fn node_id(tree: &PyTree, obj: &Bound<'_, PyAny>) -> PyResult<NodeId> {
    match as_int(obj) {
        Ok(Some(i)) if i >= 0 && (i as u64) < tree.inner.len() as u64 => Ok(i as NodeId),
        _ => Err(PyIndexError::new_err(format!(
            "node id {} out of range",
            repr(obj)
        ))),
    }
}

fn tip_codes(codes: &[Option<Bound<'_, PyAny>>]) -> PyResult<Vec<Option<u32>>> {
    codes
        .iter()
        .map(|code| match code {
            None => Ok(None),
            Some(obj) => match as_int(obj) {
                Ok(Some(i)) if (0..=i64::from(u32::MAX)).contains(&i) => Ok(Some(i as u32)),
                _ => Err(PyValueError::new_err(format!(
                    "discrete codes must be integers in [0, 2**32); got {}",
                    repr(obj)
                ))),
            },
        })
        .collect()
}

#[pyfunction]
fn viridis(t: f64) -> PyResult<Rgba> {
    core_style::viridis(t).map_err(to_py_err)
}

#[pyfunction]
fn default_palette(n_values: &Bound<'_, PyAny>) -> PyResult<Vec<&'static str>> {
    match as_int(n_values) {
        Ok(Some(n)) if n >= 0 => core_style::default_palette(n as usize).map_err(to_py_err),
        // A non-negative int too large for i64 exhausts the palette.
        Ok(None) if n_values.gt(0)? => Err(to_py_err(StyleError::PaletteExhausted)),
        _ => Err(PyValueError::new_err(format!(
            "palette size must be a non-negative integer; got {}",
            repr(n_values)
        ))),
    }
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
fn descendant_tips(tree: &PyTree, node_id: &Bound<'_, PyAny>) -> PyResult<Vec<NodeId>> {
    let node = self::node_id(tree, node_id)?;
    Ok(core_style::descendant_tips(&tree.inner, node))
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
    tip_codes: Vec<Option<Bound<'_, PyAny>>>,
) -> PyResult<DiscreteBranchCodes> {
    let codes = self::tip_codes(&tip_codes)?;
    let res = core_style::discrete_branch_codes(&tree.inner, &codes).map_err(to_py_err)?;
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
