use pyo3::prelude::*;

#[pymodule]
pub fn py_metadata(_py: Python, _m: &Bound<'_, PyModule>) -> PyResult<()> {
    Ok(())
}
