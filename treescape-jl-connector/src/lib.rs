//! treescape-jl-connector — C-ABI bindings exposing the Rust core to
//! Julia (`packages/Treescape.jl`). Mirrors the rustims `imsjl_connector`
//! pattern: one cdylib of `extern "C"` functions over opaque handles.
//!
//! Contract (docs/conventions.md, "Julia binding (v0.5 Phase 2)"):
//! every fallible call returns a status code and, on failure, an owned
//! UTF-8 message through `err`. The workspace release profile uses
//! `panic = "abort"`, so a panic here would kill the host Julia process;
//! the deny-list below keeps panicking constructs out of this crate, and
//! every pointer, string and id is validated before reaching the core.

#![deny(
    clippy::unwrap_used,
    clippy::expect_used,
    clippy::panic,
    clippy::indexing_slicing
)]
// Every `extern "C"` function dereferences raw pointers after checking
// them for null; the safety contract is the ABI documentation above.
#![allow(clippy::missing_safety_doc, clippy::not_unsafe_ptr_arg_deref)]
// C signatures take flat argument lists by design.
#![allow(clippy::too_many_arguments)]

mod ffi;
mod render;
mod style;
mod tree;

pub use ffi::{ts_abi_version, ts_string_free};
pub use render::*;
pub use style::*;
pub use tree::*;

/// Success.
pub const TS_OK: i32 = 0;
/// Null pointer, invalid UTF-8, out-of-range id, or column-length mismatch.
pub const TS_INVALID_ARGUMENT: i32 = 1;
/// Malformed Newick.
pub const TS_PARSE_ERROR: i32 = 2;
/// Styling resolution failed (NaN through viridis, palette exhausted).
pub const TS_STYLE_ERROR: i32 = 3;
/// Scene or SVG construction failed (e.g. highlight MRCA is the root).
pub const TS_RENDER_ERROR: i32 = 4;

// In-process tests of the C ABI. They call the `extern "C"` functions
// exactly as Julia does (raw pointers, out-parameters, owned strings), so
// running them under Miri and AddressSanitizer checks the unsafe
// plumbing for leaks, double frees and out-of-bounds access.
#[cfg(test)]
#[allow(clippy::unwrap_used, clippy::expect_used, clippy::indexing_slicing)]
mod tests {
    use super::*;
    use std::ffi::{c_char, CStr, CString};
    use std::ptr::{null, null_mut};

    /// Take an error/result string, freeing it through the ABI.
    fn take(p: *mut c_char) -> String {
        assert!(!p.is_null());
        let s = unsafe { CStr::from_ptr(p) }.to_str().unwrap().to_owned();
        ts_string_free(p);
        s
    }

    fn parse(src: &str) -> (i32, *mut TsTree, String) {
        let c = CString::new(src).unwrap();
        let mut tree = null_mut();
        let mut err = null_mut();
        let status = ts_tree_parse_newick(c.as_ptr(), &mut tree, &mut err);
        let msg = if err.is_null() {
            String::new()
        } else {
            take(err)
        };
        (status, tree, msg)
    }

    const NEWICK: &str = "((a:0.1,b:0.2)95:0.3,(c:0.15,(d:0.05,e:0.07)70:0.1)88:0.2);";

    #[test]
    fn parse_inspect_free() {
        let (status, tree, _) = parse(NEWICK);
        assert_eq!(status, TS_OK);
        let mut n = 0usize;
        assert_eq!(ts_tree_n_nodes(tree, &mut n, null_mut()), TS_OK);
        let mut tips = 0usize;
        assert_eq!(ts_tree_n_tips(tree, &mut tips, null_mut()), TS_OK);
        assert_eq!((n, tips), (9, 5));
        let mut buf = vec![0usize; n];
        let mut len = 0usize;
        assert_eq!(
            ts_tree_preorder(tree, buf.as_mut_ptr(), n, &mut len, null_mut()),
            TS_OK
        );
        assert_eq!(len, n);
        let mut name = null_mut();
        assert_eq!(ts_tree_tip_name(tree, 4, &mut name, null_mut()), TS_OK);
        assert_eq!(take(name), "e");
        let mut is_tip = 0u8;
        assert_eq!(
            ts_tree_is_tip(tree, n, &mut is_tip, null_mut()),
            TS_INVALID_ARGUMENT
        );
        ts_tree_free(tree);
    }

    #[test]
    fn null_and_invalid_inputs_return_status_with_message() {
        let mut tree = null_mut();
        let mut err = null_mut();
        assert_eq!(
            ts_tree_parse_newick(null(), &mut tree, &mut err),
            TS_INVALID_ARGUMENT
        );
        assert!(take(err).contains("null"));
        let bad_utf8: [u8; 4] = [b'(', 0xff, b';', 0];
        let mut err = null_mut();
        assert_eq!(
            ts_tree_parse_newick(bad_utf8.as_ptr().cast(), &mut tree, &mut err),
            TS_INVALID_ARGUMENT
        );
        assert!(take(err).contains("UTF-8"));
        let (status, tree, msg) = parse("a];");
        assert_eq!((status, tree.is_null()), (TS_PARSE_ERROR, true));
        assert!(msg.contains("unmatched"));
        // Null out-pointer: the tree built internally must be freed, not leaked.
        let c = CString::new(NEWICK).unwrap();
        assert_eq!(
            ts_tree_parse_newick(c.as_ptr(), null_mut(), null_mut()),
            TS_INVALID_ARGUMENT
        );
        ts_tree_free(null_mut());
        ts_style_free(null_mut());
        ts_string_free(null_mut());
    }

    // Miri: builder plumbing (pointer arrays, owned strings, free) is
    // checked here without rendering. Rendering parses the embedded font,
    // which takes Miri tens of minutes and is safe code; the render tests
    // below are skipped under Miri.
    #[test]
    fn style_builder_plumbing() {
        let style = ts_style_new();
        let names: Vec<CString> = ["a", "b", "c"]
            .iter()
            .map(|s| CString::new(*s).unwrap())
            .collect();
        let ptrs: Vec<*const c_char> = names.iter().map(|s| s.as_ptr()).collect();
        assert_eq!(
            ts_style_add_highlight(style, ptrs.as_ptr(), 3, 1, 2, 3, 4, null_mut()),
            TS_OK
        );
        let mut err = null_mut();
        assert_eq!(
            ts_style_add_highlight(style, null(), 2, 1, 2, 3, 4, &mut err),
            TS_INVALID_ARGUMENT
        );
        take(err);
        let a = CString::new("a").unwrap();
        assert_eq!(
            ts_style_set_tip_color(style, a.as_ptr(), 9, 9, 9, 255, null_mut()),
            TS_OK
        );
        assert_eq!(
            ts_style_set_branch_color(style, 2, 1, 2, 3, 255, null_mut()),
            TS_OK
        );
        assert_eq!(ts_style_set_branch_width(style, 1, 2.5, null_mut()), TS_OK);
        let label = CString::new("0.1").unwrap();
        assert_eq!(
            ts_style_set_scale_bar(style, 0.1, label.as_ptr(), null_mut()),
            TS_OK
        );
        assert_eq!(
            ts_style_set_support_labels(style, 1, 80.0, null_mut()),
            TS_OK
        );
        let mut opts = TsCircularSceneOptions {
            px_per_r: 0.0,
            padding: 0.0,
            font_size: 0.0,
            label_offset: 0.0,
            stroke_width: 0.0,
            start_angle: 0.0,
            sweep_total: 0.0,
        };
        assert_eq!(
            ts_circular_scene_options_default(&mut opts, null_mut()),
            TS_OK
        );
        assert_eq!(opts.px_per_r, 60.0);
        ts_style_free(style);
    }

    #[test]
    #[cfg_attr(miri, ignore = "renders: font parsing is too slow under Miri")]
    fn styled_render_roundtrip_and_errors() {
        let (_, tree, _) = parse(NEWICK);
        let style = ts_style_new();
        let names: Vec<CString> = ["a", "b"]
            .iter()
            .map(|s| CString::new(*s).unwrap())
            .collect();
        let ptrs: Vec<*const c_char> = names.iter().map(|s| s.as_ptr()).collect();
        assert_eq!(
            ts_style_add_highlight(style, ptrs.as_ptr(), 2, 1, 2, 3, 4, null_mut()),
            TS_OK
        );
        let a = CString::new("a").unwrap();
        assert_eq!(
            ts_style_set_tip_color(style, a.as_ptr(), 9, 9, 9, 255, null_mut()),
            TS_OK
        );
        assert_eq!(ts_style_set_branch_width(style, 1, 2.5, null_mut()), TS_OK);
        let label = CString::new("0.1").unwrap();
        assert_eq!(
            ts_style_set_scale_bar(style, 0.1, label.as_ptr(), null_mut()),
            TS_OK
        );
        assert_eq!(
            ts_style_set_support_labels(style, 1, 80.0, null_mut()),
            TS_OK
        );

        let mut opts = TsSceneOptions {
            px_per_x: 0.0,
            px_per_y: 0.0,
            padding: 0.0,
            font_size: 0.0,
            label_offset: 0.0,
            stroke_width: 0.0,
        };
        assert_eq!(ts_scene_options_default(&mut opts, null_mut()), TS_OK);
        let mut svg = null_mut();
        assert_eq!(
            ts_render_rectangular_svg(tree, &opts, style, &mut svg, null_mut()),
            TS_OK
        );
        assert!(take(svg).contains("<svg"));
        let mut svg = null_mut();
        assert_eq!(
            ts_render_circular_svg(tree, null(), style, &mut svg, null_mut()),
            TS_OK
        );
        assert!(take(svg).contains("<svg"));

        // Branch id the tree does not have.
        assert_eq!(
            ts_style_set_branch_color(style, 99, 0, 0, 0, 255, null_mut()),
            TS_OK
        );
        let mut err = null_mut();
        let mut svg = null_mut();
        assert_eq!(
            ts_render_rectangular_svg(tree, null(), style, &mut svg, &mut err),
            TS_INVALID_ARGUMENT
        );
        assert!(svg.is_null());
        assert!(take(err).contains("out of range"));
        ts_style_free(style);
        ts_tree_free(tree);
    }

    #[test]
    fn resolvers_write_exactly_their_buffers() {
        let (_, tree, _) = parse(NEWICK);
        let mut n = 0usize;
        ts_tree_n_nodes(tree, &mut n, null_mut());
        let values = [0.1, 0.9, 0.4, 0.4, 0.7];
        let present = [1u8, 1, 0, 1, 1];
        let (mut lo, mut hi) = (0.0, 0.0);
        assert_eq!(
            ts_value_range(
                values.as_ptr(),
                present.as_ptr(),
                5,
                0,
                0.0,
                0,
                0.0,
                &mut lo,
                &mut hi,
                null_mut()
            ),
            TS_OK
        );
        assert_eq!((lo, hi), (0.1, 0.9));
        let (mut t, mut has) = ([0.0; 5], [0u8; 5]);
        assert_eq!(
            ts_continuous_tip_t(
                tree,
                values.as_ptr(),
                present.as_ptr(),
                5,
                lo,
                hi,
                t.as_mut_ptr(),
                has.as_mut_ptr(),
                null_mut()
            ),
            TS_OK
        );
        assert_eq!(has, [1, 1, 0, 1, 1]);
        let (mut w, mut whas) = (vec![0.0; n], vec![0u8; n]);
        assert_eq!(
            ts_branch_widths(
                tree,
                values.as_ptr(),
                present.as_ptr(),
                5,
                lo,
                hi,
                1.0,
                4.0,
                w.as_mut_ptr(),
                whas.as_mut_ptr(),
                null_mut()
            ),
            TS_OK
        );
        let codes = [0u32, 0, 1, 1, 1];
        let (mut code, mut state) = (vec![0u32; n], vec![0u8; n]);
        assert_eq!(
            ts_discrete_branch_codes(
                tree,
                codes.as_ptr(),
                [1u8; 5].as_ptr(),
                5,
                code.as_mut_ptr(),
                state.as_mut_ptr(),
                null_mut()
            ),
            TS_OK
        );
        let mut err = null_mut();
        assert_eq!(
            ts_continuous_branch_t(
                tree,
                values.as_ptr(),
                present.as_ptr(),
                4,
                lo,
                hi,
                w.as_mut_ptr(),
                whas.as_mut_ptr(),
                &mut err
            ),
            TS_INVALID_ARGUMENT
        );
        assert!(take(err).contains("column has 4"));
        let mut rgba = [0u8; 4];
        let mut err = null_mut();
        assert_eq!(
            ts_viridis(f64::NAN, rgba.as_mut_ptr(), &mut err),
            TS_STYLE_ERROR
        );
        assert_eq!(take(err), "cannot convert float NaN to integer");
        let mut pal = [0u8; 12];
        assert_eq!(ts_default_palette(3, pal.as_mut_ptr(), null_mut()), TS_OK);
        assert_eq!(&pal[..4], &[0x4e, 0x79, 0xa7, 255]);
        ts_tree_free(tree);
    }

    #[test]
    fn oversized_and_misaligned_buffers_are_rejected() {
        let values = [0.5f64; 4];
        let present = [1u8; 4];
        let (mut lo, mut hi) = (0.0, 0.0);
        let mut err = null_mut();
        // A length whose byte size overflows isize must not reach from_raw_parts.
        assert_eq!(
            ts_value_range(
                values.as_ptr(),
                present.as_ptr(),
                usize::MAX / 2,
                0,
                0.0,
                0,
                0.0,
                &mut lo,
                &mut hi,
                &mut err
            ),
            TS_INVALID_ARGUMENT
        );
        assert!(take(err).contains("too large"));
        #[repr(align(8))]
        struct Aligned([u8; 64]);
        let bytes = Aligned([0u8; 64]);
        let misaligned = bytes.0[1..].as_ptr().cast::<f64>();
        let mut err = null_mut();
        assert_eq!(
            ts_value_range(
                misaligned,
                present.as_ptr(),
                2,
                0,
                0.0,
                0,
                0.0,
                &mut lo,
                &mut hi,
                &mut err
            ),
            TS_INVALID_ARGUMENT
        );
        assert!(take(err).contains("misaligned"));
    }

    #[test]
    fn invalid_out_and_err_pointers_are_rejected_without_leaks_or_writes() {
        let (_, tree, _) = parse(NEWICK);
        // Null out_svg: rejected before rendering, nothing allocated.
        let mut err = null_mut();
        assert_eq!(
            ts_render_rectangular_svg(tree, null(), null(), null_mut(), &mut err),
            TS_INVALID_ARGUMENT
        );
        assert!(take(err).contains("out_svg"));
        let mut name_err = null_mut();
        assert_eq!(
            ts_tree_node_name(tree, 0, null_mut(), &mut name_err),
            TS_INVALID_ARGUMENT
        );
        take(name_err);
        // Misaligned err: status only, no write.
        #[repr(align(8))]
        struct Aligned([u8; 16]);
        let mut buf = Aligned([0u8; 16]);
        let bad_err = buf.0[1..].as_mut_ptr().cast::<*mut c_char>();
        let mut n = 0usize;
        assert_eq!(
            ts_tree_n_nodes(null(), &mut n, bad_err),
            TS_INVALID_ARGUMENT
        );
        assert_eq!(buf.0, [0u8; 16]);
        // Misaligned opts: an error, not a silent fallback to defaults.
        let mut svg = null_mut();
        let mut err = null_mut();
        let bad_opts = buf.0[1..].as_ptr().cast::<TsSceneOptions>();
        assert_eq!(
            ts_render_rectangular_svg(tree, bad_opts, null(), &mut svg, &mut err),
            TS_INVALID_ARGUMENT
        );
        assert!(svg.is_null());
        assert!(take(err).contains("misaligned"));
        ts_tree_free(tree);
    }

    #[test]
    #[cfg_attr(miri, ignore = "allocates 16 MiB")]
    fn oversized_newick_is_rejected_before_parsing() {
        let big = "a".repeat(tree::MAX_NEWICK_BYTES + 1) + ";";
        let (status, tree, msg) = parse(&big);
        assert_eq!((status, tree.is_null()), (TS_INVALID_ARGUMENT, true));
        assert!(msg.contains("limit"));
    }

    #[test]
    #[cfg_attr(miri, ignore = "renders: font parsing is too slow under Miri")]
    fn non_finite_geometry_is_a_render_error() {
        let (_, tree, _) = parse(NEWICK);
        let mut opts = TsSceneOptions {
            px_per_x: 60.0,
            px_per_y: 18.0,
            padding: f64::NAN,
            font_size: 12.0,
            label_offset: 4.0,
            stroke_width: 1.0,
        };
        let (mut svg, mut err) = (null_mut(), null_mut());
        assert_eq!(
            ts_render_rectangular_svg(tree, &opts, null(), &mut svg, &mut err),
            TS_RENDER_ERROR
        );
        assert!(svg.is_null());
        assert!(take(err).contains("non-finite"));
        opts.padding = 12.0;
        let (mut svg, mut err) = (null_mut(), null_mut());
        assert_eq!(
            ts_render_rectangular_svg(tree, &opts, null(), &mut svg, &mut err),
            TS_OK
        );
        take(svg);
        ts_tree_free(tree);
    }

    #[test]
    fn nul_bytes_in_names_do_not_truncate_or_fail() {
        // Quoted Newick names may contain any character except NUL (a C
        // string cannot carry it), so to_c_string must never return null.
        let s = ffi::to_c_string("a\u{0}b");
        assert!(!s.is_null());
        assert_eq!(take(s), "a\u{fffd}b");
    }
}
