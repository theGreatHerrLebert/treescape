//! PyO3 bindings for `treescape_core::layout`.

use pyo3::prelude::*;

use treescape_core::layout::rectangular::{
    rectangular_layout as core_rectangular_layout, Layout,
};

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

#[pyfunction]
fn rectangular_layout(tree: &PyTree) -> PyLayout {
    PyLayout {
        inner: core_rectangular_layout(&tree.inner),
    }
}

#[pymodule]
pub fn py_layout(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyLayout>()?;
    m.add_function(wrap_pyfunction!(rectangular_layout, m)?)?;
    Ok(())
}
