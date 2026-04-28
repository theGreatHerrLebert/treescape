//! PyO3 bindings for metadata joins. v0.2 deliverable; the v0.1
//! TreePlot grammar handles only structural rendering, so this module
//! is a placeholder so the connector layout matches rustims'
//! ``imspy_connector`` shape and stays stable across releases.

use pyo3::prelude::*;

#[pymodule]
pub fn py_metadata(_m: &Bound<'_, PyModule>) -> PyResult<()> {
    Ok(())
}
