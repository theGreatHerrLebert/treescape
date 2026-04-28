//! treescape-render: deterministic SVG emitter + themes.

pub mod svg;
pub mod style;

pub use svg::{render_svg, SvgError};
pub use style::default_theme;

use treescape_core::layout::rectangular::{
    build_rectangular_scene, rectangular_layout, SceneOptions,
};
use treescape_core::layout::scene::Scene;
use treescape_core::tree::Tree;

/// Convenience: layout + scene + SVG bytes in one call.
pub fn render_rectangular(tree: &Tree, opts: &SceneOptions) -> Result<String, SvgError> {
    let layout = rectangular_layout(tree);
    let scene = build_rectangular_scene(tree, &layout, opts);
    render_svg(&scene)
}

/// Convenience: build the scene without emitting SVG bytes. Useful
/// for the `tip-count-invariant` claim runner which inspects the
/// scene graph directly.
pub fn build_scene(tree: &Tree, opts: &SceneOptions) -> Scene {
    let layout = rectangular_layout(tree);
    build_rectangular_scene(tree, &layout, opts)
}
