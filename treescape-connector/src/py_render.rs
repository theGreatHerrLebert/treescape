//! PyO3 bindings for `treescape_render` and the scene-graph types in
//! `treescape_core::layout::scene`.

use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;

use std::collections::HashMap;

use treescape_core::layout::circular::CircularSceneOptions as CoreCircularSceneOptions;
use treescape_core::layout::rectangular::{
    build_rectangular_scene_with_style, CladeHighlight, SceneOptions as CoreSceneOptions,
    StyleSpec as CoreStyleSpec,
};
use treescape_core::layout::scene::{Color as CoreColor, Scene};
use treescape_core::layout::rectangular::rectangular_layout;
use treescape_render::{
    build_circular_scene_, build_scene, render_circular, render_rectangular, render_svg,
    text_width as core_text_width,
};

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
        label_offset = 4.0,
        stroke_width = 1.0,
    ))]
    fn new(
        px_per_x: f64,
        px_per_y: f64,
        padding: f64,
        font_size: f64,
        label_offset: f64,
        stroke_width: f64,
    ) -> Self {
        // v0.2 dropped the `avg_glyph_width` knob: tip-label widths
        // are measured via fontdue against the bundled DejaVu Sans.
        // The legacy 0.6-em fallback is still reachable via the bare
        // `treescape_core::layout::rectangular::build_rectangular_scene`
        // function but is not surfaced through the Python API.
        Self {
            inner: CoreSceneOptions {
                px_per_x,
                px_per_y,
                padding,
                font_size,
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
    #[getter]
    fn label_offset(&self) -> f64 {
        self.inner.label_offset
    }
    #[getter]
    fn stroke_width(&self) -> f64 {
        self.inner.stroke_width
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

/// `(r, g, b, a)` color spec passed from Python. Avoids the
/// type-complexity lint on the styled-render signatures below.
type Rgba = (u8, u8, u8, u8);
/// `(tip_names, color)` highlight spec.
type HighlightSpec = (Vec<String>, Rgba);

/// Render rectangular SVG with v0.2 Phase-3 styling: clade highlights
/// and per-tip color overrides. `highlights` is a list of
/// `(tip_names, (r, g, b, a))`; `tip_colors` is `{tip_name: (r,g,b,a)}`.
///
/// Backs the user-facing `TreePlot.highlight_clade` and
/// `TreePlot.color_tips` grammar.
#[pyfunction]
#[pyo3(signature = (tree, opts = None, highlights = Vec::new(), tip_colors = HashMap::new()))]
fn render_rectangular_styled_svg(
    tree: &PyTree,
    opts: Option<&PySceneOptions>,
    highlights: Vec<HighlightSpec>,
    tip_colors: HashMap<String, Rgba>,
) -> PyResult<String> {
    let default_opts = CoreSceneOptions::default();
    let opts_ref = opts.map(|o| &o.inner).unwrap_or(&default_opts);

    let mut style = CoreStyleSpec::default();
    for (tip_names, (r, g, b, a)) in highlights {
        style.highlights.push(CladeHighlight {
            tip_names,
            fill: CoreColor::rgba(r, g, b, a),
        });
    }
    for (name, (r, g, b, a)) in tip_colors {
        style.tip_colors.insert(name, CoreColor::rgba(r, g, b, a));
    }

    let layout = rectangular_layout(&tree.inner);
    let scene = build_rectangular_scene_with_style(
        &tree.inner,
        &layout,
        opts_ref,
        &core_text_width,
        &style,
    );
    render_svg(&scene).map_err(|e| PyRuntimeError::new_err(e.to_string()))
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

/// Width in pixels of `text` rendered at `font_size`, using fontdue
/// against the bundled DejaVu Sans. Exposed primarily for the
/// `treescape-text-width-vs-fontdue` oracle test.
#[pyfunction]
fn text_width(text: &str, font_size: f64) -> f64 {
    core_text_width(text, font_size)
}

#[pyclass(name = "CircularSceneOptions", module = "treescape_connector.py_render")]
#[derive(Clone)]
pub struct PyCircularSceneOptions {
    pub(crate) inner: CoreCircularSceneOptions,
}

#[pymethods]
impl PyCircularSceneOptions {
    #[new]
    #[pyo3(signature = (
        px_per_r = 60.0,
        padding = 12.0,
        font_size = 12.0,
        label_offset = 4.0,
        stroke_width = 1.0,
        start_angle = std::f64::consts::FRAC_PI_2,
        sweep_total = std::f64::consts::TAU,
    ))]
    fn new(
        px_per_r: f64,
        padding: f64,
        font_size: f64,
        label_offset: f64,
        stroke_width: f64,
        start_angle: f64,
        sweep_total: f64,
    ) -> Self {
        Self {
            inner: CoreCircularSceneOptions {
                px_per_r,
                padding,
                font_size,
                label_offset,
                stroke_width,
                start_angle,
                sweep_total,
                ..CoreCircularSceneOptions::default()
            },
        }
    }

    #[getter]
    fn px_per_r(&self) -> f64 {
        self.inner.px_per_r
    }
    #[getter]
    fn padding(&self) -> f64 {
        self.inner.padding
    }
    #[getter]
    fn font_size(&self) -> f64 {
        self.inner.font_size
    }
    #[getter]
    fn label_offset(&self) -> f64 {
        self.inner.label_offset
    }
    #[getter]
    fn stroke_width(&self) -> f64 {
        self.inner.stroke_width
    }
    #[getter]
    fn start_angle(&self) -> f64 {
        self.inner.start_angle
    }
    #[getter]
    fn sweep_total(&self) -> f64 {
        self.inner.sweep_total
    }
}

#[pyfunction]
#[pyo3(signature = (tree, opts = None))]
fn render_circular_svg(
    tree: &PyTree,
    opts: Option<&PyCircularSceneOptions>,
) -> PyResult<String> {
    let default = CoreCircularSceneOptions::default();
    let opts_ref = opts.map(|o| &o.inner).unwrap_or(&default);
    render_circular(&tree.inner, opts_ref)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))
}

#[pyfunction]
#[pyo3(signature = (tree, opts = None))]
fn build_circular_scene(
    tree: &PyTree,
    opts: Option<&PyCircularSceneOptions>,
) -> PyScene {
    let default = CoreCircularSceneOptions::default();
    let opts_ref = opts.map(|o| &o.inner).unwrap_or(&default);
    PyScene {
        inner: build_circular_scene_(&tree.inner, opts_ref),
    }
}

#[pymodule]
pub fn py_render(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PySceneOptions>()?;
    m.add_class::<PyCircularSceneOptions>()?;
    m.add_class::<PyScene>()?;
    m.add_function(wrap_pyfunction!(render_rectangular_svg, m)?)?;
    m.add_function(wrap_pyfunction!(render_rectangular_styled_svg, m)?)?;
    m.add_function(wrap_pyfunction!(build_rectangular_scene, m)?)?;
    m.add_function(wrap_pyfunction!(render_circular_svg, m)?)?;
    m.add_function(wrap_pyfunction!(build_circular_scene, m)?)?;
    m.add_function(wrap_pyfunction!(text_width, m)?)?;
    Ok(())
}
