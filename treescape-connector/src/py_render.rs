use pyo3::prelude::*;

#[pymodule]
pub fn py_render(_py: Python, _m: &Bound<'_, PyModule>) -> PyResult<()> {
    Ok(())
}
