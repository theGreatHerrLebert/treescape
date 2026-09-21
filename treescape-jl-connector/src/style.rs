//! Style builder handle (the render-time `StyleSpec`) and the
//! `treescape_core::style` resolvers (v0.5 Phase 1), with the same
//! semantics `treescape_connector.py_style` exposes to Python.

use std::ffi::c_char;

use treescape_core::layout::rectangular::{CladeHighlight, ScaleBar, StyleSpec, SupportLabelSpec};
use treescape_core::layout::scene::Color;
use treescape_core::style as core_style;

use crate::ffi::{
    column, finish, handle, handle_mut, out_slice, slice_arg, str_arg, write_out, Failure,
    FfiResult,
};
use crate::tree::TsTree;
use crate::TS_STYLE_ERROR;

/// Opaque style handle: everything the styled render paths consume.
#[derive(Default)]
pub struct TsStyle {
    pub(crate) spec: StyleSpec,
}

fn style_err(e: core_style::StyleError) -> Failure {
    match e {
        core_style::StyleError::ColumnLength { .. } => Failure::invalid(e.to_string()),
        _ => Failure::new(TS_STYLE_ERROR, e.to_string()),
    }
}

#[no_mangle]
pub extern "C" fn ts_style_new() -> *mut TsStyle {
    Box::into_raw(Box::default())
}

/// Release a style. Null is a no-op.
#[no_mangle]
pub extern "C" fn ts_style_free(style: *mut TsStyle) {
    if !style.is_null() {
        // SAFETY: came from `Box::into_raw` in `ts_style_new`.
        drop(unsafe { Box::from_raw(style) });
    }
}

/// Highlight the clade at `MRCA(names)`.
#[no_mangle]
pub extern "C" fn ts_style_add_highlight(
    style: *mut TsStyle,
    names: *const *const c_char,
    n_names: usize,
    r: u8,
    g: u8,
    b: u8,
    a: u8,
    err: *mut *mut c_char,
) -> i32 {
    let run = || {
        let style = handle_mut(style, "style")?;
        let tip_names = slice_arg(names, n_names, "names")?
            .iter()
            .map(|&p| str_arg(p, "tip name").map(str::to_owned))
            .collect::<FfiResult<Vec<String>>>()?;
        style.spec.highlights.push(CladeHighlight {
            tip_names,
            fill: Color::rgba(r, g, b, a),
        });
        Ok(())
    };
    finish(run(), err)
}

#[no_mangle]
pub extern "C" fn ts_style_set_tip_color(
    style: *mut TsStyle,
    name: *const c_char,
    r: u8,
    g: u8,
    b: u8,
    a: u8,
    err: *mut *mut c_char,
) -> i32 {
    let run = || {
        let style = handle_mut(style, "style")?;
        let name = str_arg(name, "name")?.to_owned();
        style.spec.tip_colors.insert(name, Color::rgba(r, g, b, a));
        Ok(())
    };
    finish(run(), err)
}

/// Color the branch above `node`. Ids are checked against the tree at
/// render time.
#[no_mangle]
pub extern "C" fn ts_style_set_branch_color(
    style: *mut TsStyle,
    node: usize,
    r: u8,
    g: u8,
    b: u8,
    a: u8,
    err: *mut *mut c_char,
) -> i32 {
    let run = || {
        handle_mut(style, "style")?
            .spec
            .branch_colors
            .insert(node, Color::rgba(r, g, b, a));
        Ok(())
    };
    finish(run(), err)
}

#[no_mangle]
pub extern "C" fn ts_style_set_branch_width(
    style: *mut TsStyle,
    node: usize,
    width: f64,
    err: *mut *mut c_char,
) -> i32 {
    let run = || {
        handle_mut(style, "style")?
            .spec
            .branch_widths
            .insert(node, width);
        Ok(())
    };
    finish(run(), err)
}

#[no_mangle]
pub extern "C" fn ts_style_set_scale_bar(
    style: *mut TsStyle,
    length: f64,
    label: *const c_char,
    err: *mut *mut c_char,
) -> i32 {
    let run = || {
        let style = handle_mut(style, "style")?;
        let label = str_arg(label, "label")?.to_owned();
        style.spec.scale_bar = Some(ScaleBar { length, label });
        Ok(())
    };
    finish(run(), err)
}

/// Render internal-node names as support labels, optionally only those
/// parsing as numbers `>= min_value` (when `has_min != 0`).
#[no_mangle]
pub extern "C" fn ts_style_set_support_labels(
    style: *mut TsStyle,
    has_min: u8,
    min_value: f64,
    err: *mut *mut c_char,
) -> i32 {
    let run = || {
        handle_mut(style, "style")?.spec.support_labels = Some(SupportLabelSpec {
            min_value: (has_min != 0).then_some(min_value),
        });
        Ok(())
    };
    finish(run(), err)
}

// ---------------------------------------------------------------------------
// Resolvers
// ---------------------------------------------------------------------------

/// Viridis color for `t` into `out_rgba[4]`.
#[no_mangle]
pub extern "C" fn ts_viridis(t: f64, out_rgba: *mut u8, err: *mut *mut c_char) -> i32 {
    let run = || {
        let (r, g, b, a) = core_style::viridis(t).map_err(style_err)?;
        out_slice(out_rgba, 4, "out_rgba")?.copy_from_slice(&[r, g, b, a]);
        Ok(())
    };
    finish(run(), err)
}

fn parse_hex(hex: &str) -> FfiResult<[u8; 4]> {
    let digits = hex.trim_start_matches('#');
    let byte = |i: usize| {
        digits
            .get(i..i + 2)
            .and_then(|s| u8::from_str_radix(s, 16).ok())
            .ok_or_else(|| Failure::invalid(format!("bad palette color {hex}")))
    };
    Ok([byte(0)?, byte(2)?, byte(4)?, 255])
}

/// Default Tableau-10 palette for `n` values into `out_rgba[4 * n]`.
#[no_mangle]
pub extern "C" fn ts_default_palette(n: usize, out_rgba: *mut u8, err: *mut *mut c_char) -> i32 {
    let run = || {
        let palette = core_style::default_palette(n).map_err(style_err)?;
        let out = out_slice(out_rgba, 4 * palette.len(), "out_rgba")?;
        for (chunk, hex) in out.as_chunks_mut::<4>().0.iter_mut().zip(palette) {
            chunk.copy_from_slice(&parse_hex(hex)?);
        }
        Ok(())
    };
    finish(run(), err)
}

#[no_mangle]
pub extern "C" fn ts_value_range(
    values: *const f64,
    present: *const u8,
    len: usize,
    has_vmin: u8,
    vmin: f64,
    has_vmax: u8,
    vmax: f64,
    out_lo: *mut f64,
    out_hi: *mut f64,
    err: *mut *mut c_char,
) -> i32 {
    let run = || {
        let col = column(values, present, len)?;
        let (lo, hi) = core_style::value_range(
            &col,
            (has_vmin != 0).then_some(vmin),
            (has_vmax != 0).then_some(vmax),
        );
        write_out(out_lo, lo, "out_lo")?;
        write_out(out_hi, hi, "out_hi")
    };
    finish(run(), err)
}

/// Per-tip `t`, aligned to tip order: `out_t[k]` is valid iff `out_has[k]`.
#[no_mangle]
pub extern "C" fn ts_continuous_tip_t(
    tree: *const TsTree,
    values: *const f64,
    present: *const u8,
    len: usize,
    lo: f64,
    hi: f64,
    out_t: *mut f64,
    out_has: *mut u8,
    err: *mut *mut c_char,
) -> i32 {
    let run = || {
        let t = handle(tree, "tree")?;
        let col = column(values, present, len)?;
        let resolved = core_style::continuous_tip_t(&t.tree, &col, lo, hi).map_err(style_err)?;
        let out_t = out_slice(out_t, len, "out_t")?;
        let out_has = out_slice(out_has, len, "out_has")?;
        out_has.fill(0);
        // `resolved` lists present tips in tip order.
        let mut resolved = resolved.into_iter();
        for ((slot_t, slot_has), value) in out_t.iter_mut().zip(out_has.iter_mut()).zip(&col) {
            if value.is_some() {
                if let Some((_, tval)) = resolved.next() {
                    *slot_t = tval;
                    *slot_has = 1;
                }
            }
        }
        Ok(())
    };
    finish(run(), err)
}

/// Write per-node results into `out_*[n_nodes]` buffers.
fn scatter(
    t: &TsTree,
    pairs: Vec<(usize, f64)>,
    out_vals: *mut f64,
    out_has: *mut u8,
) -> FfiResult<()> {
    let n = t.tree.len();
    let out_vals = out_slice(out_vals, n, "out values")?;
    let out_has = out_slice(out_has, n, "out_has")?;
    out_has.fill(0);
    for (node, v) in pairs {
        if let (Some(slot), Some(flag)) = (out_vals.get_mut(node), out_has.get_mut(node)) {
            *slot = v;
            *flag = 1;
        }
    }
    Ok(())
}

/// Per-branch `t` from subtree means, indexed by node id.
#[no_mangle]
pub extern "C" fn ts_continuous_branch_t(
    tree: *const TsTree,
    values: *const f64,
    present: *const u8,
    len: usize,
    lo: f64,
    hi: f64,
    out_t: *mut f64,
    out_has: *mut u8,
    err: *mut *mut c_char,
) -> i32 {
    let run = || {
        let t = handle(tree, "tree")?;
        let col = column(values, present, len)?;
        let pairs = core_style::continuous_branch_t(&t.tree, &col, lo, hi).map_err(style_err)?;
        scatter(t, pairs, out_t, out_has)
    };
    finish(run(), err)
}

/// Per-branch widths from subtree means, indexed by node id.
#[no_mangle]
pub extern "C" fn ts_branch_widths(
    tree: *const TsTree,
    values: *const f64,
    present: *const u8,
    len: usize,
    lo: f64,
    hi: f64,
    wmin: f64,
    wmax: f64,
    out_w: *mut f64,
    out_has: *mut u8,
    err: *mut *mut c_char,
) -> i32 {
    let run = || {
        let t = handle(tree, "tree")?;
        let col = column(values, present, len)?;
        let pairs =
            core_style::branch_widths(&t.tree, &col, lo, hi, wmin, wmax).map_err(style_err)?;
        scatter(t, pairs, out_w, out_has)
    };
    finish(run(), err)
}

/// Branch state per node id: `out_state` is 0 (default: root or no
/// data), 1 (colored with `out_code`), or 2 (non-monophyletic).
#[no_mangle]
pub extern "C" fn ts_discrete_branch_codes(
    tree: *const TsTree,
    codes: *const u32,
    present: *const u8,
    len: usize,
    out_code: *mut u32,
    out_state: *mut u8,
    err: *mut *mut c_char,
) -> i32 {
    let run = || {
        let t = handle(tree, "tree")?;
        let col = column(codes, present, len)?;
        let res = core_style::discrete_branch_codes(&t.tree, &col).map_err(style_err)?;
        let n = t.tree.len();
        let out_code = out_slice(out_code, n, "out_code")?;
        let out_state = out_slice(out_state, n, "out_state")?;
        out_code.fill(0);
        out_state.fill(0);
        for (node, code) in res.colored {
            if let (Some(c), Some(s)) = (out_code.get_mut(node), out_state.get_mut(node)) {
                *c = code;
                *s = 1;
            }
        }
        for node in res.non_monophyletic {
            if let Some(s) = out_state.get_mut(node) {
                *s = 2;
            }
        }
        Ok(())
    };
    finish(run(), err)
}
