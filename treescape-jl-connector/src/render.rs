//! Scene options and SVG rendering. Mirrors the four PyO3 render paths
//! (`render_{rectangular,circular}{,_styled}_svg`) so Julia and Python
//! produce the same bytes for the same inputs.

use std::ffi::c_char;

use treescape_core::layout::circular::CircularSceneOptions;
use treescape_core::layout::rectangular::{
    build_rectangular_scene_with_style, rectangular_layout, SceneOptions,
};
use treescape_render::{
    render_circular, render_circular_styled, render_rectangular, render_svg, text_width,
};

use crate::ffi::{finish, handle, to_c_string, write_out, Failure, FfiResult};
use crate::style::TsStyle;
use crate::tree::TsTree;
use crate::TS_RENDER_ERROR;

/// Rectangular scene options (the knobs `SceneOptions` exposes to Python).
#[repr(C)]
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct TsSceneOptions {
    pub px_per_x: f64,
    pub px_per_y: f64,
    pub padding: f64,
    pub font_size: f64,
    pub label_offset: f64,
    pub stroke_width: f64,
}

/// Circular scene options (the knobs `CircularSceneOptions` exposes to Python).
#[repr(C)]
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct TsCircularSceneOptions {
    pub px_per_r: f64,
    pub padding: f64,
    pub font_size: f64,
    pub label_offset: f64,
    pub stroke_width: f64,
    pub start_angle: f64,
    pub sweep_total: f64,
}

impl From<&TsSceneOptions> for SceneOptions {
    fn from(o: &TsSceneOptions) -> Self {
        SceneOptions {
            px_per_x: o.px_per_x,
            px_per_y: o.px_per_y,
            padding: o.padding,
            font_size: o.font_size,
            label_offset: o.label_offset,
            stroke_width: o.stroke_width,
            ..SceneOptions::default()
        }
    }
}

impl From<&TsCircularSceneOptions> for CircularSceneOptions {
    fn from(o: &TsCircularSceneOptions) -> Self {
        CircularSceneOptions {
            px_per_r: o.px_per_r,
            padding: o.padding,
            font_size: o.font_size,
            label_offset: o.label_offset,
            stroke_width: o.stroke_width,
            start_angle: o.start_angle,
            sweep_total: o.sweep_total,
            ..CircularSceneOptions::default()
        }
    }
}

#[no_mangle]
pub extern "C" fn ts_scene_options_default(out: *mut TsSceneOptions, err: *mut *mut c_char) -> i32 {
    let d = SceneOptions::default();
    let opts = TsSceneOptions {
        px_per_x: d.px_per_x,
        px_per_y: d.px_per_y,
        padding: d.padding,
        font_size: d.font_size,
        label_offset: d.label_offset,
        stroke_width: d.stroke_width,
    };
    finish(write_out(out, opts, "out"), err)
}

#[no_mangle]
pub extern "C" fn ts_circular_scene_options_default(
    out: *mut TsCircularSceneOptions,
    err: *mut *mut c_char,
) -> i32 {
    let d = CircularSceneOptions::default();
    let opts = TsCircularSceneOptions {
        px_per_r: d.px_per_r,
        padding: d.padding,
        font_size: d.font_size,
        label_offset: d.label_offset,
        stroke_width: d.stroke_width,
        start_angle: d.start_angle,
        sweep_total: d.sweep_total,
    };
    finish(write_out(out, opts, "out"), err)
}

/// Branch styling is keyed by node id; reject ids the tree does not have.
fn check_style_ids(tree: &TsTree, style: &TsStyle) -> FfiResult<()> {
    let spec = &style.spec;
    for &id in spec.branch_colors.keys().chain(spec.branch_widths.keys()) {
        tree.check_node(id)?;
    }
    Ok(())
}

fn render_err(e: impl std::fmt::Display) -> Failure {
    Failure::new(TS_RENDER_ERROR, e.to_string())
}

/// Rectangular SVG. `opts` null → defaults; `style` null → the unstyled
/// path (Python uses it when no styling was requested).
#[no_mangle]
pub extern "C" fn ts_render_rectangular_svg(
    tree: *const TsTree,
    opts: *const TsSceneOptions,
    style: *const TsStyle,
    out_svg: *mut *mut c_char,
    err: *mut *mut c_char,
) -> i32 {
    let run = || {
        let t = handle(tree, "tree")?;
        let opts: SceneOptions = handle(opts, "opts")
            .map(SceneOptions::from)
            .unwrap_or_default();
        let svg = if style.is_null() {
            render_rectangular(&t.tree, &opts).map_err(render_err)?
        } else {
            let style = handle(style, "style")?;
            check_style_ids(t, style)?;
            let layout = rectangular_layout(&t.tree);
            let scene = build_rectangular_scene_with_style(
                &t.tree,
                &layout,
                &opts,
                &text_width,
                &style.spec,
            );
            render_svg(&scene).map_err(render_err)?
        };
        write_out(out_svg, to_c_string(&svg), "out_svg")
    };
    finish(run(), err)
}

/// Circular SVG. `opts` null → defaults; `style` null → the unstyled path.
#[no_mangle]
pub extern "C" fn ts_render_circular_svg(
    tree: *const TsTree,
    opts: *const TsCircularSceneOptions,
    style: *const TsStyle,
    out_svg: *mut *mut c_char,
    err: *mut *mut c_char,
) -> i32 {
    let run = || {
        let t = handle(tree, "tree")?;
        let opts: CircularSceneOptions = handle(opts, "opts")
            .map(CircularSceneOptions::from)
            .unwrap_or_default();
        let svg = if style.is_null() {
            render_circular(&t.tree, &opts).map_err(render_err)?
        } else {
            let style = handle(style, "style")?;
            check_style_ids(t, style)?;
            render_circular_styled(&t.tree, &opts, &style.spec).map_err(render_err)?
        };
        write_out(out_svg, to_c_string(&svg), "out_svg")
    };
    finish(run(), err)
}
