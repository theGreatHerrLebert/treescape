//! treescape-render: deterministic SVG emitter + themes.

pub mod style;
pub mod svg;
pub mod text;

pub use style::default_theme;
pub use svg::{render_svg, SvgError};
pub use text::text_width;

use treescape_core::layout::circular::{
    build_circular_scene_with_measurer, circular_layout_with, CircularSceneOptions,
};
use treescape_core::layout::rectangular::{
    build_rectangular_scene_with_measurer, rectangular_layout, SceneOptions,
};
use treescape_core::layout::scene::Scene;
use treescape_core::tree::Tree;

/// Convenience: layout + scene + SVG bytes in one call. Uses the
/// fontdue-backed [`text_width`] measurer so canvas widths reflect
/// real glyph metrics — see the `treescape-text-width-vs-fontdue`
/// EVIDENT claim.
pub fn render_rectangular(tree: &Tree, opts: &SceneOptions) -> Result<String, SvgError> {
    let layout = rectangular_layout(tree);
    let scene = build_rectangular_scene_with_measurer(tree, &layout, opts, &text_width);
    render_svg(&scene)
}

/// Convenience: build the scene without emitting SVG bytes. Useful
/// for the `tip-count-invariant` claim runner which inspects the
/// scene graph directly. Uses the fontdue-backed measurer.
pub fn build_scene(tree: &Tree, opts: &SceneOptions) -> Scene {
    let layout = rectangular_layout(tree);
    build_rectangular_scene_with_measurer(tree, &layout, opts, &text_width)
}

/// Circular layout + scene + SVG bytes in one call. Honors
/// `opts.start_angle` and `opts.sweep_total` so fan layouts (e.g.
/// `sweep_total = π`) actually sweep less than a full circle.
pub fn render_circular(tree: &Tree, opts: &CircularSceneOptions) -> Result<String, SvgError> {
    let layout = circular_layout_with(tree, opts.start_angle, opts.sweep_total);
    let scene = build_circular_scene_with_measurer(tree, &layout, opts, &text_width);
    render_svg(&scene)
}

pub fn build_circular_scene_(tree: &Tree, opts: &CircularSceneOptions) -> Scene {
    let layout = circular_layout_with(tree, opts.start_angle, opts.sweep_total);
    build_circular_scene_with_measurer(tree, &layout, opts, &text_width)
}
