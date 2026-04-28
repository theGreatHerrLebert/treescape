//! PyO3 bindings for `treescape_core::tree` and `treescape_core::newick`.

use pyo3::exceptions::{PyIndexError, PyValueError};
use pyo3::prelude::*;

use treescape_core::ladderize as core_ladderize;
use treescape_core::newick;
use treescape_core::tree::Tree;

#[pyclass(name = "Tree", module = "treescape_connector.py_tree")]
#[derive(Clone)]
pub struct PyTree {
    pub(crate) inner: Tree,
}

#[pymethods]
impl PyTree {
    #[new]
    fn new() -> Self {
        Self {
            inner: Tree::default(),
        }
    }

    #[staticmethod]
    fn parse_newick(s: &str) -> PyResult<Self> {
        newick::parse(s)
            .map(|inner| Self { inner })
            .map_err(|e| PyValueError::new_err(e.to_string()))
    }

    fn write_newick(&self) -> String {
        newick::write(&self.inner)
    }

    fn topology_hash(&self) -> u64 {
        self.inner.topology_hash()
    }

    fn ladderize(&mut self, ascending: bool) {
        core_ladderize::ladderize(&mut self.inner, ascending);
    }

    fn tip_order(&self) -> Vec<String> {
        core_ladderize::tip_order(&self.inner)
    }

    fn preorder(&self) -> Vec<usize> {
        self.inner.preorder()
    }

    fn postorder(&self) -> Vec<usize> {
        self.inner.postorder()
    }

    fn name(&self, id: usize) -> PyResult<String> {
        self.inner
            .name
            .get(id)
            .cloned()
            .ok_or_else(|| PyIndexError::new_err(format!("node id out of range: {id}")))
    }

    fn branch_len(&self, id: usize) -> PyResult<f64> {
        self.inner
            .branch_len
            .get(id)
            .copied()
            .ok_or_else(|| PyIndexError::new_err(format!("node id out of range: {id}")))
    }

    fn is_tip(&self, id: usize) -> PyResult<bool> {
        self.inner
            .is_tip
            .get(id)
            .copied()
            .ok_or_else(|| PyIndexError::new_err(format!("node id out of range: {id}")))
    }

    fn parent(&self, id: usize) -> PyResult<Option<usize>> {
        self.inner
            .parent
            .get(id)
            .copied()
            .ok_or_else(|| PyIndexError::new_err(format!("node id out of range: {id}")))
    }

    fn children(&self, id: usize) -> PyResult<Vec<usize>> {
        self.inner
            .children
            .get(id)
            .cloned()
            .ok_or_else(|| PyIndexError::new_err(format!("node id out of range: {id}")))
    }

    #[getter]
    fn root(&self) -> Option<usize> {
        self.inner.root
    }

    #[getter]
    fn n_nodes(&self) -> usize {
        self.inner.len()
    }

    fn n_tips(&self) -> usize {
        self.inner.is_tip.iter().filter(|t| **t).count()
    }

    fn __repr__(&self) -> String {
        format!(
            "Tree(n_nodes={}, n_tips={}, root={:?})",
            self.inner.len(),
            self.inner.is_tip.iter().filter(|t| **t).count(),
            self.inner.root,
        )
    }
}

#[pymodule]
pub fn py_tree(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyTree>()?;
    Ok(())
}
