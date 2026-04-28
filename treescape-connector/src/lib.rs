//! treescape-connector — PyO3 bindings exposing the Rust core to Python.
//!
//! Mirrors the rustims `imspy_connector` pattern: one cdylib, multiple
//! `#[pymodule]` submodules registered via `wrap_pymodule!`. Submodule
//! implementations land in Phase 4.

use pyo3::prelude::*;
use pyo3::wrap_pymodule;

pub mod py_tree;
pub mod py_layout;
pub mod py_render;
pub mod py_metadata;

#[pymodule]
fn treescape_connector(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_wrapped(wrap_pymodule!(py_tree::py_tree))?;
    m.add_wrapped(wrap_pymodule!(py_layout::py_layout))?;
    m.add_wrapped(wrap_pymodule!(py_render::py_render))?;
    m.add_wrapped(wrap_pymodule!(py_metadata::py_metadata))?;
    Ok(())
}
