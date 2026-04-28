//! Circular phylogram layout — polar coordinates per node.
//!
//! Conventions owned by the Python reference at
//! `packages/treescape-reference/.../layout.py::circular_layout` and
//! documented in `docs/conventions.md`.
//!
//! Backs the EVIDENT claims `treescape-circular-layout-vs-ete3` and
//! `treescape-circular-layout-vs-ggtree`. Rust↔Python parity within
//! `1e-9` is part of `treescape-layout-rust-vs-reference` (extended in
//! v0.2 to cover circular layouts).

use std::f64::consts::PI;

use crate::clades::{clade_tips, find_mrca};
use crate::layout::rectangular::StyleSpec;
use crate::layout::scene::{Canvas, Color, Scene, SceneItem, TextAnchor};
use crate::tree::Tree;

/// Polar coordinates for every node, parallel-indexed by node id.
/// `r[i]` is cumulative branch length from the root; `theta[i]` is in
/// radians. The Cartesian projection used by the renderer is
/// `x = cx + r·cos(θ); y = cy − r·sin(θ)`.
#[derive(Debug, Clone, Default)]
pub struct CircularLayout {
    pub r: Vec<f64>,
    pub theta: Vec<f64>,
}

impl CircularLayout {
    pub fn len(&self) -> usize {
        self.r.len()
    }

    pub fn is_empty(&self) -> bool {
        self.r.is_empty()
    }

    /// Project to `(name, r, theta)` for every named tip, in postorder.
    pub fn tips_by_name(&self, tree: &Tree) -> Vec<(String, f64, f64)> {
        let mut out = Vec::new();
        for id in tree.postorder() {
            if !tree.is_tip[id] || tree.name[id].is_empty() {
                continue;
            }
            out.push((tree.name[id].clone(), self.r[id], self.theta[id]));
        }
        out
    }
}

/// Compute `(r, θ)` for every node in a circular phylogram.
///
/// `start_angle` defaults to `π/2` (12 o'clock); `sweep_total`
/// defaults to `2π` (full circle). Tips are placed clockwise as the
/// pre-order leaf index increases — `θ_i = start_angle − (i / N) ·
/// sweep_total`. Internal nodes get the wrap-aware vector mean of
/// their children's angles (essential when children straddle the
/// 0/2π wrap point).
pub fn circular_layout_with(tree: &Tree, start_angle: f64, sweep_total: f64) -> CircularLayout {
    let n = tree.len();
    let mut layout = CircularLayout {
        r: vec![0.0; n],
        theta: vec![0.0; n],
    };

    let Some(root) = tree.root else {
        return layout;
    };

    let preorder = tree.preorder();

    layout.r[root] = 0.0;
    for &id in &preorder {
        for &c in &tree.children[id] {
            layout.r[c] = layout.r[id] + tree.branch_len[c];
        }
    }

    let tips: Vec<usize> = preorder
        .iter()
        .copied()
        .filter(|&i| tree.is_tip[i])
        .collect();
    let n_tips = tips.len();

    if n_tips == 0 {
        layout.theta[root] = start_angle;
        return layout;
    }
    if n_tips == 1 {
        layout.theta[tips[0]] = start_angle;
    } else {
        let inv_n = 1.0 / n_tips as f64;
        for (i, &tip) in tips.iter().enumerate() {
            layout.theta[tip] = start_angle - (i as f64) * inv_n * sweep_total;
        }
    }

    for id in tree.postorder() {
        if tree.is_tip[id] {
            continue;
        }
        let cs = &tree.children[id];
        if cs.is_empty() {
            continue;
        }
        let mut sx = 0.0_f64;
        let mut sy = 0.0_f64;
        for &c in cs {
            sx += layout.theta[c].cos();
            sy += layout.theta[c].sin();
        }
        layout.theta[id] = sy.atan2(sx);
    }

    layout
}

/// Defaults: `start_angle = π/2` (12 o'clock), `sweep_total = 2π`.
pub fn circular_layout(tree: &Tree) -> CircularLayout {
    circular_layout_with(tree, PI / 2.0, 2.0 * PI)
}

/// Knobs for [`build_circular_scene`]. Reuses fields from the
/// rectangular [`crate::layout::rectangular::SceneOptions`] where the
/// meaning is the same — `px_per_x` is reused as pixels per unit
/// radius, since both axes carry cumulative branch length.
#[derive(Debug, Clone)]
pub struct CircularSceneOptions {
    pub px_per_r: f64,
    pub padding: f64,
    pub font_size: f64,
    pub label_offset: f64,
    pub stroke: Color,
    pub stroke_width: f64,
    pub label_color: Color,
    pub start_angle: f64,
    pub sweep_total: f64,
}

impl Default for CircularSceneOptions {
    fn default() -> Self {
        Self {
            px_per_r: 60.0,
            padding: 12.0,
            font_size: 12.0,
            label_offset: 4.0,
            stroke: Color::black(),
            stroke_width: 1.0,
            label_color: Color::black(),
            start_angle: PI / 2.0,
            sweep_total: 2.0 * PI,
        }
    }
}

/// Build a circular phylogram scene: radial branch segments, arc
/// spines connecting children of internal nodes, and rotated tip
/// labels. The renderer projects polar `(r, θ)` to Cartesian via
/// `x = cx + r·cos(θ); y = cy − r·sin(θ)`.
///
/// `measure_width` measures tip-label widths in pixels — pass the
/// fontdue-backed measurer from `treescape-render` for proper canvas
/// sizing.
pub fn build_circular_scene_with_measurer(
    tree: &Tree,
    layout: &CircularLayout,
    opts: &CircularSceneOptions,
    measure_width: &dyn Fn(&str, f64) -> f64,
) -> Scene {
    if tree.is_empty() || layout.is_empty() {
        return Scene {
            canvas: Canvas {
                width: 0.0,
                height: 0.0,
            },
            items: Vec::new(),
        };
    }

    let max_r = layout
        .r
        .iter()
        .enumerate()
        .filter(|(i, _)| tree.is_tip[*i])
        .map(|(_, &r)| r)
        .fold(0.0_f64, f64::max);

    let max_label_px = tree
        .name
        .iter()
        .enumerate()
        .filter(|(i, _)| tree.is_tip[*i])
        .map(|(_, n)| measure_width(n, opts.font_size))
        .fold(0.0_f64, f64::max);

    let radius_px = max_r * opts.px_per_r;
    let half = opts.padding + radius_px + opts.label_offset + max_label_px;
    let canvas_size = 2.0 * half;
    let canvas = Canvas {
        width: canvas_size,
        height: canvas_size,
    };
    let cx = half;
    let cy = half;

    let project = |r: f64, theta: f64| -> (f64, f64) {
        (
            cx + r * opts.px_per_r * theta.cos(),
            cy - r * opts.px_per_r * theta.sin(),
        )
    };

    let mut items = Vec::new();

    for id in tree.preorder() {
        let cs = &tree.children[id];
        if cs.is_empty() {
            continue;
        }
        let parent_r = layout.r[id];

        for &child in cs {
            let cr = layout.r[child];
            let cth = layout.theta[child];
            let (x1, y1) = project(parent_r, cth);
            let (x2, y2) = project(cr, cth);
            items.push(SceneItem::Line {
                x1,
                y1,
                x2,
                y2,
                stroke: opts.stroke,
                stroke_width: opts.stroke_width,
            });
        }

        if parent_r > 0.0 && cs.len() >= 2 {
            let mut min_th = f64::INFINITY;
            let mut max_th = f64::NEG_INFINITY;
            for &c in cs {
                let th = layout.theta[c];
                if th < min_th {
                    min_th = th;
                }
                if th > max_th {
                    max_th = th;
                }
            }
            let span = max_th - min_th;
            let (x1, y1) = project(parent_r, min_th);
            let (x2, y2) = project(parent_r, max_th);
            items.push(SceneItem::Arc {
                x1,
                y1,
                x2,
                y2,
                radius: parent_r * opts.px_per_r,
                large_arc: span > PI,
                // Increasing θ from min to max = CCW visually in our
                // SVG projection (since y = cy − r·sin θ). SVG sweep=0
                // (sweep_clockwise=false) selects the CCW arc.
                sweep_clockwise: false,
                stroke: opts.stroke,
                stroke_width: opts.stroke_width,
            });
        }
    }

    for id in tree.preorder() {
        if !tree.is_tip[id] || tree.name[id].is_empty() {
            continue;
        }
        let r = layout.r[id];
        let theta = layout.theta[id];
        let ux = theta.cos();
        let uy = -theta.sin();
        let (px, py) = project(r, theta);
        let tx = px + opts.label_offset * ux;
        let ty = py + opts.label_offset * uy;
        let deg = theta.to_degrees();
        let (anchor, rotation_deg) = if ux >= 0.0 {
            (TextAnchor::Start, -deg)
        } else {
            (TextAnchor::End, -deg + 180.0)
        };
        items.push(SceneItem::Text {
            x: tx,
            y: ty,
            text: tree.name[id].clone(),
            font_size: opts.font_size,
            color: opts.label_color,
            anchor,
            is_tip_label: true,
            rotation_deg,
        });
    }

    Scene { canvas, items }
}

/// Convenience: 0.6-em monospace fallback measurer baked in for
/// callers that don't want to pull a font. Same legacy fallback
/// pattern as [`crate::layout::rectangular::build_rectangular_scene`].
pub fn build_circular_scene(
    tree: &Tree,
    layout: &CircularLayout,
    opts: &CircularSceneOptions,
) -> Scene {
    let measure = |s: &str, fs: f64| s.chars().count() as f64 * fs * 0.6;
    build_circular_scene_with_measurer(tree, layout, opts, &measure)
}

/// Build a circular scene with v0.3+v0.4 styling.
///
/// v0.3 Phase 3 introduced `style.highlights` (annular sectors behind
/// the scene). v0.4 Phase 1 added `style.tip_colors` (per-Text fill)
/// and `style.branch_colors` (radial parent→child Line stroke; arc
/// spine stays default per the locked convention in
/// `docs/conventions.md`). Other [`StyleSpec`] fields (scale_bar,
/// support_labels) are reserved for v0.4 Phase 2; the user-facing
/// `TreePlot` still raises `NotImplementedError` for them on
/// circular.
///
/// Returns `Err` when a highlight's MRCA is the tree's root — under
/// the v0.3 convention that case covers the whole tree visually and
/// is loud-rejected rather than silently emitting a whole-canvas
/// sector. Unknown tip names in a highlight are skipped (matching
/// the rectangular path's behavior).
pub fn build_circular_scene_with_style(
    tree: &Tree,
    layout: &CircularLayout,
    opts: &CircularSceneOptions,
    measure_width: &dyn Fn(&str, f64) -> f64,
    style: &StyleSpec,
) -> Result<Scene, String> {
    if tree.is_empty() || layout.is_empty() {
        return Ok(Scene {
            canvas: Canvas {
                width: 0.0,
                height: 0.0,
            },
            items: Vec::new(),
        });
    }

    let max_r = layout
        .r
        .iter()
        .enumerate()
        .filter(|(i, _)| tree.is_tip[*i])
        .map(|(_, &r)| r)
        .fold(0.0_f64, f64::max);
    let max_label_px = tree
        .name
        .iter()
        .enumerate()
        .filter(|(i, _)| tree.is_tip[*i])
        .map(|(_, n)| measure_width(n, opts.font_size))
        .fold(0.0_f64, f64::max);

    let radius_px = max_r * opts.px_per_r;
    let half = opts.padding + radius_px + opts.label_offset + max_label_px;
    let canvas_size = 2.0 * half;
    let canvas = Canvas {
        width: canvas_size,
        height: canvas_size,
    };
    let cx = half;
    let cy = half;
    let r_outer_px = radius_px + opts.label_offset + max_label_px;

    let project = |r: f64, theta: f64| -> (f64, f64) {
        (
            cx + r * opts.px_per_r * theta.cos(),
            cy - r * opts.px_per_r * theta.sin(),
        )
    };

    let root = match tree.root {
        Some(r) => r,
        None => return Ok(Scene { canvas, items: Vec::new() }),
    };

    let mut items: Vec<SceneItem> = Vec::new();

    // Highlights (annular sectors) emitted first so they render behind
    // branches and labels. MRCA == root → loud reject.
    for h in &style.highlights {
        let tip_refs: Vec<&str> = h.tip_names.iter().map(|s| s.as_str()).collect();
        let mrca = match find_mrca(tree, &tip_refs) {
            Ok(m) => m,
            Err(_) => continue,
        };
        if mrca == root {
            return Err(
                "circular highlight_clade(MRCA == root) covers the whole tree; \
                 drop the highlight or pick a deeper clade"
                    .to_string(),
            );
        }
        let clade = clade_tips(tree, mrca);
        if clade.is_empty() {
            continue;
        }
        let mut theta_min = f64::INFINITY;
        let mut theta_max = f64::NEG_INFINITY;
        for &id in &clade {
            let t = layout.theta[id];
            if t < theta_min {
                theta_min = t;
            }
            if t > theta_max {
                theta_max = t;
            }
        }
        let r_inner_px = layout.r[mrca] * opts.px_per_r;
        items.push(SceneItem::AnnularSector {
            cx,
            cy,
            r_inner: r_inner_px,
            r_outer: r_outer_px,
            theta_min,
            theta_max,
            fill: h.fill,
        });
    }

    // Radial branch lines + arc spines. Per the v0.4 Phase 1
    // convention, style.branch_colors override the radial Line stroke
    // (parent→child); the arc spine stays at opts.stroke.
    for id in tree.preorder() {
        let cs = &tree.children[id];
        if cs.is_empty() {
            continue;
        }
        let parent_r = layout.r[id];

        for &child in cs {
            let cr = layout.r[child];
            let cth = layout.theta[child];
            let (x1, y1) = project(parent_r, cth);
            let (x2, y2) = project(cr, cth);
            let stroke = style
                .branch_colors
                .get(&child)
                .copied()
                .unwrap_or(opts.stroke);
            items.push(SceneItem::Line {
                x1,
                y1,
                x2,
                y2,
                stroke,
                stroke_width: opts.stroke_width,
            });
        }

        if parent_r > 0.0 && cs.len() >= 2 {
            let mut min_th = f64::INFINITY;
            let mut max_th = f64::NEG_INFINITY;
            for &c in cs {
                let th = layout.theta[c];
                if th < min_th {
                    min_th = th;
                }
                if th > max_th {
                    max_th = th;
                }
            }
            let span = max_th - min_th;
            let (x1, y1) = project(parent_r, min_th);
            let (x2, y2) = project(parent_r, max_th);
            items.push(SceneItem::Arc {
                x1,
                y1,
                x2,
                y2,
                radius: parent_r * opts.px_per_r,
                large_arc: span > PI,
                sweep_clockwise: false,
                stroke: opts.stroke,
                stroke_width: opts.stroke_width,
            });
        }
    }

    // Tip labels — per-tip color override via style.tip_colors keyed
    // by name (portable across Python ref / Rust).
    for id in tree.preorder() {
        if !tree.is_tip[id] || tree.name[id].is_empty() {
            continue;
        }
        let r = layout.r[id];
        let theta = layout.theta[id];
        let ux = theta.cos();
        let uy = -theta.sin();
        let (px, py) = project(r, theta);
        let tx = px + opts.label_offset * ux;
        let ty = py + opts.label_offset * uy;
        let deg = theta.to_degrees();
        let (anchor, rotation_deg) = if ux >= 0.0 {
            (TextAnchor::Start, -deg)
        } else {
            (TextAnchor::End, -deg + 180.0)
        };
        let color = style
            .tip_colors
            .get(&tree.name[id])
            .copied()
            .unwrap_or(opts.label_color);
        items.push(SceneItem::Text {
            x: tx,
            y: ty,
            text: tree.name[id].clone(),
            font_size: opts.font_size,
            color,
            anchor,
            is_tip_label: true,
            rotation_deg,
        });
    }

    // v0.4 Phase 2: support labels — upright text at projected
    // internal-node positions (rotation_deg = 0), middle-anchored.
    if let Some(support) = &style.support_labels {
        for id in tree.preorder() {
            if tree.is_tip[id] || tree.name[id].is_empty() {
                continue;
            }
            if let Some(min_value) = support.min_value {
                let Ok(value) = tree.name[id].parse::<f64>() else {
                    continue;
                };
                if value < min_value {
                    continue;
                }
            }
            let r = layout.r[id];
            let theta = layout.theta[id];
            let (sx, sy) = project(r, theta);
            items.push(SceneItem::Text {
                x: sx,
                y: sy,
                text: tree.name[id].clone(),
                font_size: opts.font_size,
                color: opts.label_color,
                anchor: TextAnchor::Middle,
                is_tip_label: false,
                rotation_deg: 0.0,
            });
        }
    }

    // v0.4 Phase 2: bottom-right radial scale bar. Right endpoint
    // anchored at canvas_width - padding, extends leftward; ticks at
    // both ends, label centered below. Same scene primitives as the
    // rectangular scale bar — only the position differs.
    if let Some(scale_bar) = &style.scale_bar {
        if scale_bar.length > 0.0 {
            let bar_x2 = canvas.width - opts.padding;
            let bar_x1 = bar_x2 - scale_bar.length * opts.px_per_r;
            let bar_y = canvas.height - opts.padding - opts.font_size * 1.2;
            let tick = (opts.font_size * 0.35).max(3.0);
            items.push(SceneItem::Line {
                x1: bar_x1,
                y1: bar_y,
                x2: bar_x2,
                y2: bar_y,
                stroke: opts.stroke,
                stroke_width: opts.stroke_width,
            });
            for x in [bar_x1, bar_x2] {
                items.push(SceneItem::Line {
                    x1: x,
                    y1: bar_y - tick * 0.5,
                    x2: x,
                    y2: bar_y + tick * 0.5,
                    stroke: opts.stroke,
                    stroke_width: opts.stroke_width,
                });
            }
            items.push(SceneItem::Text {
                x: (bar_x1 + bar_x2) * 0.5,
                y: bar_y + opts.font_size * 1.2,
                text: scale_bar.label.clone(),
                font_size: opts.font_size,
                color: opts.label_color,
                anchor: TextAnchor::Middle,
                is_tip_label: false,
                rotation_deg: 0.0,
            });
        }
    }

    Ok(Scene { canvas, items })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::newick::parse;
    use std::collections::HashMap;

    fn approx(a: f64, b: f64, tol: f64) -> bool {
        (a - b).abs() < tol
    }

    fn tip_map(t: &Tree, l: &CircularLayout) -> HashMap<String, (f64, f64)> {
        l.tips_by_name(t)
            .into_iter()
            .map(|(n, r, th)| (n, (r, th)))
            .collect()
    }

    #[test]
    fn two_tips_full_circle() {
        let t = parse("(a:1.0,b:1.0);").unwrap();
        let l = circular_layout(&t);
        let m = tip_map(&t, &l);
        // Tip a at start_angle = π/2 (top); tip b at π/2 - π = -π/2.
        assert!(approx(m["a"].0, 1.0, 1e-12));
        assert!(approx(m["a"].1, PI / 2.0, 1e-12));
        assert!(approx(m["b"].0, 1.0, 1e-12));
        assert!(approx(m["b"].1, -PI / 2.0, 1e-12));
    }

    #[test]
    fn balanced_4_evenly_spaced() {
        let t = parse("((a:1.0,b:1.0):1.0,(c:1.0,d:1.0):1.0);").unwrap();
        let l = circular_layout(&t);
        let m = tip_map(&t, &l);
        // 4 tips → 90° apart, clockwise from 12 o'clock.
        for (name, expected_deg) in [("a", 90.0), ("b", 0.0), ("c", -90.0), ("d", -180.0)] {
            let expected = (expected_deg as f64).to_radians();
            assert!(
                approx(m[name].1, expected, 1e-12),
                "{name}: expected {expected} got {}",
                m[name].1
            );
            assert!(approx(m[name].0, 2.0, 1e-12));
        }
    }

    #[test]
    fn trifurcation_120_apart() {
        let t = parse("(a:1.0,b:1.0,c:1.0);").unwrap();
        let l = circular_layout(&t);
        let m = tip_map(&t, &l);
        for (name, expected_deg) in [("a", 90.0), ("b", -30.0), ("c", -150.0)] {
            assert!(approx(m[name].1, (expected_deg as f64).to_radians(), 1e-12));
        }
    }

    #[test]
    fn root_radius_is_zero() {
        let t = parse("((a:1.0,b:1.0):2.0,(c:3.0,d:4.0):0.5);").unwrap();
        let l = circular_layout(&t);
        assert_eq!(l.r[t.root.unwrap()], 0.0);
    }

    #[test]
    fn r_is_cumulative_branch_length() {
        // Same as rectangular's x: parent + branch_len.
        let t = parse("((a:1.0,b:1.0):2.0,(c:3.0,d:4.0):0.5);").unwrap();
        let l = circular_layout(&t);
        let m = tip_map(&t, &l);
        // a's path: root → 2.0 → 1.0 → tip, total 3.0
        assert!(approx(m["a"].0, 3.0, 1e-12));
        // d's path: root → 0.5 → 4.0 → tip, total 4.5
        assert!(approx(m["d"].0, 4.5, 1e-12));
    }

    #[test]
    fn empty_tree_yields_empty_layout() {
        let t = Tree::default();
        let l = circular_layout(&t);
        assert!(l.is_empty());
    }

    #[test]
    fn fan_layout_half_circle() {
        let t = parse("((a:1.0,b:1.0):1.0,(c:1.0,d:1.0):1.0);").unwrap();
        // Half-fan: sweep_total = π. 4 tips, so 45° apart (π/4 rad).
        let l = circular_layout_with(&t, PI / 2.0, PI);
        let m = tip_map(&t, &l);
        for (name, expected_deg) in [("a", 90.0), ("b", 45.0), ("c", 0.0), ("d", -45.0)] {
            assert!(
                approx(m[name].1, (expected_deg as f64).to_radians(), 1e-12),
                "{name}: expected {}° got {}°",
                expected_deg as f64,
                m[name].1.to_degrees()
            );
        }
    }
}
