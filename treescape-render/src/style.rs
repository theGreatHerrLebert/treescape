//! Default theme.
//!
//! v0.1 ships one theme: black branches and labels on a transparent
//! canvas. Color palettes for metadata mapping land in v0.2.

use treescape_core::layout::rectangular::SceneOptions;

pub fn default_theme() -> SceneOptions {
    SceneOptions::default()
}
