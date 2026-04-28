//! treescape-connector — PyO3 bindings exposing the Rust core to Python.
//!
//! Mirrors the rustims `imspy_connector` pattern: one cdylib, multiple
//! `#[pymodule]` submodules registered via `wrap_pymodule!`. After
//! registration we also insert each submodule into `sys.modules` so
//! `from treescape_connector.py_tree import Tree` resolves cleanly,
//! not just `from treescape_connector import py_tree`.

use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3::wrap_pymodule;

pub mod py_layout;
pub mod py_metadata;
pub mod py_render;
pub mod py_tree;

#[pymodule]
fn treescape_connector(py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_wrapped(wrap_pymodule!(py_tree::py_tree))?;
    m.add_wrapped(wrap_pymodule!(py_layout::py_layout))?;
    m.add_wrapped(wrap_pymodule!(py_render::py_render))?;
    m.add_wrapped(wrap_pymodule!(py_metadata::py_metadata))?;

    // Register submodules in sys.modules so they are importable as
    // dotted paths.
    let sys_modules = py
        .import("sys")?
        .getattr("modules")?
        .downcast_into::<PyDict>()?;
    for name in ["py_tree", "py_layout", "py_render", "py_metadata"] {
        let submodule = m.getattr(name)?;
        sys_modules.set_item(format!("treescape_connector.{name}"), submodule)?;
    }

    Ok(())
}
