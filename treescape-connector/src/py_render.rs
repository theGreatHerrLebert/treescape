//! PyO3 bindings for `treescape_render` and the scene-graph types in
//! `treescape_core::layout::scene`.

use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;

use treescape_core::layout::rectangular::SceneOptions as CoreSceneOptions;
use treescape_core::layout::scene::Scene;
use treescape_render::{build_scene, render_rectangular};

use crate::py_tree::PyTree;

#[pyclass(name = "SceneOptions", module = "treescape_connector.py_render")]
#[derive(Clone)]
pub struct PySceneOptions {
    pub(crate) inner: CoreSceneOptions,
}

#[pymethods]
impl PySceneOptions {
    #[new]
    #[pyo3(signature = (
        px_per_x = 60.0,
        px_per_y = 18.0,
        padding = 12.0,
        font_size = 12.0,
        avg_glyph_width = 0.6,
        label_offset = 4.0,
        stroke_width = 1.0,
    ))]
    fn new(
        px_per_x: f64,
        px_per_y: f64,
        padding: f64,
        font_size: f64,
        avg_glyph_width: f64,
        label_offset: f64,
        stroke_width: f64,
    ) -> Self {
        Self {
            inner: CoreSceneOptions {
                px_per_x,
                px_per_y,
                padding,
                font_size,
                avg_glyph_width,
                label_offset,
                stroke_width,
                ..CoreSceneOptions::default()
            },
        }
    }

    #[getter]
    fn px_per_x(&self) -> f64 {
        self.inner.px_per_x
    }
    #[getter]
    fn px_per_y(&self) -> f64 {
        self.inner.px_per_y
    }
    #[getter]
    fn padding(&self) -> f64 {
        self.inner.padding
    }
    #[getter]
    fn font_size(&self) -> f64 {
        self.inner.font_size
    }
}

#[pyclass(name = "Scene", module = "treescape_connector.py_render")]
pub struct PyScene {
    pub(crate) inner: Scene,
}

#[pymethods]
impl PyScene {
    #[getter]
    fn canvas_width(&self) -> f64 {
        self.inner.canvas.width
    }

    #[getter]
    fn canvas_height(&self) -> f64 {
        self.inner.canvas.height
    }

    #[getter]
    fn n_items(&self) -> usize {
        self.inner.items.len()
    }

    fn count_tip_labels(&self) -> usize {
        self.inner.count_tip_labels()
    }

    fn coords_within_canvas(&self, eps: f64) -> bool {
        self.inner.coords_within_canvas(eps)
    }

    fn __repr__(&self) -> String {
        format!(
            "Scene(canvas={}x{}, n_items={})",
            self.inner.canvas.width,
            self.inner.canvas.height,
            self.inner.items.len(),
        )
    }
}

#[pyfunction]
#[pyo3(signature = (tree, opts = None))]
fn render_rectangular_svg(tree: &PyTree, opts: Option<&PySceneOptions>) -> PyResult<String> {
    let default = CoreSceneOptions::default();
    let opts_ref = opts.map(|o| &o.inner).unwrap_or(&default);
    render_rectangular(&tree.inner, opts_ref)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))
}

#[pyfunction]
#[pyo3(signature = (tree, opts = None))]
fn build_rectangular_scene(tree: &PyTree, opts: Option<&PySceneOptions>) -> PyScene {
    let default = CoreSceneOptions::default();
    let opts_ref = opts.map(|o| &o.inner).unwrap_or(&default);
    PyScene {
        inner: build_scene(&tree.inner, opts_ref),
    }
}

#[pymodule]
pub fn py_render(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PySceneOptions>()?;
    m.add_class::<PyScene>()?;
    m.add_function(wrap_pyfunction!(render_rectangular_svg, m)?)?;
    m.add_function(wrap_pyfunction!(build_rectangular_scene, m)?)?;
    Ok(())
}
