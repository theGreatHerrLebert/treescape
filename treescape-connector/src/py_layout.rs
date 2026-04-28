//! PyO3 bindings for `treescape_core::layout`.

use pyo3::prelude::*;

use treescape_core::layout::circular::{
    circular_layout as core_circular_layout, circular_layout_with as core_circular_layout_with,
    CircularLayout,
};
use treescape_core::layout::rectangular::{rectangular_layout as core_rectangular_layout, Layout};

use crate::py_tree::PyTree;

#[pyclass(name = "Layout", module = "treescape_connector.py_layout")]
pub struct PyLayout {
    pub(crate) inner: Layout,
}

#[pymethods]
impl PyLayout {
    #[getter]
    fn x(&self) -> Vec<f64> {
        self.inner.x.clone()
    }

    #[getter]
    fn y(&self) -> Vec<f64> {
        self.inner.y.clone()
    }

    #[getter]
    fn n_nodes(&self) -> usize {
        self.inner.len()
    }

    fn tips_by_name(&self, tree: &PyTree) -> Vec<(String, f64, f64)> {
        self.inner.tips_by_name(&tree.inner)
    }

    fn __repr__(&self) -> String {
        format!("Layout(n_nodes={})", self.inner.len())
    }
}

#[pyclass(name = "CircularLayout", module = "treescape_connector.py_layout")]
pub struct PyCircularLayout {
    pub(crate) inner: CircularLayout,
}

#[pymethods]
impl PyCircularLayout {
    #[getter]
    fn r(&self) -> Vec<f64> {
        self.inner.r.clone()
    }

    #[getter]
    fn theta(&self) -> Vec<f64> {
        self.inner.theta.clone()
    }

    #[getter]
    fn n_nodes(&self) -> usize {
        self.inner.len()
    }

    fn tips_by_name(&self, tree: &PyTree) -> Vec<(String, f64, f64)> {
        self.inner.tips_by_name(&tree.inner)
    }

    fn __repr__(&self) -> String {
        format!("CircularLayout(n_nodes={})", self.inner.len())
    }
}

#[pyfunction]
fn rectangular_layout(tree: &PyTree) -> PyLayout {
    PyLayout {
        inner: core_rectangular_layout(&tree.inner),
    }
}

#[pyfunction]
#[pyo3(signature = (tree, start_angle = None, sweep_total = None))]
fn circular_layout(
    tree: &PyTree,
    start_angle: Option<f64>,
    sweep_total: Option<f64>,
) -> PyCircularLayout {
    let inner = match (start_angle, sweep_total) {
        (None, None) => core_circular_layout(&tree.inner),
        (Some(s), Some(t)) => core_circular_layout_with(&tree.inner, s, t),
        (Some(s), None) => core_circular_layout_with(&tree.inner, s, std::f64::consts::TAU),
        (None, Some(t)) => core_circular_layout_with(&tree.inner, std::f64::consts::FRAC_PI_2, t),
    };
    PyCircularLayout { inner }
}

#[pymodule]
pub fn py_layout(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyLayout>()?;
    m.add_class::<PyCircularLayout>()?;
    m.add_function(wrap_pyfunction!(rectangular_layout, m)?)?;
    m.add_function(wrap_pyfunction!(circular_layout, m)?)?;
    Ok(())
}
