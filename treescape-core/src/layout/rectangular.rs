//! Rectangular phylogram layout + scene construction.
//!
//! Conventions are owned by the Python reference at
//! `packages/treescape-reference/src/treescape_reference/layout.py`
//! and documented in `docs/conventions.md`.

use std::collections::HashMap;

use crate::clades::{clade_tips, find_mrca};
use crate::layout::scene::{Canvas, Color, Scene, SceneItem, TextAnchor};
use crate::tree::Tree;

/// One clade-highlight rectangle to draw behind the branches.
#[derive(Debug, Clone)]
pub struct CladeHighlight {
    pub tip_names: Vec<String>,
    pub fill: Color,
}

/// A rectangular phylogram scale bar, expressed in branch-length units.
#[derive(Debug, Clone)]
pub struct ScaleBar {
    pub length: f64,
    pub label: String,
}

/// Internal-node label rendering options.
#[derive(Debug, Clone, Default)]
pub struct SupportLabelSpec {
    pub min_value: Option<f64>,
}

/// Style overrides that the renderer applies on top of the geometric
/// scene. Default = no styling (existing rectangular SVG bytes).
#[derive(Debug, Default, Clone)]
pub struct StyleSpec {
    pub highlights: Vec<CladeHighlight>,
    pub tip_colors: HashMap<String, Color>,
    pub branch_colors: HashMap<usize, Color>,
    /// v0.4 Phase 3: numeric-metadata-driven branch stroke width.
    /// Keyed by child node id (the parent→child branch). Missing
    /// entries fall back to `SceneOptions.stroke_width`. Sibling
    /// connectors (rectangular vertical spine, circular arc) are
    /// not affected by this map.
    pub branch_widths: HashMap<usize, f64>,
    pub scale_bar: Option<ScaleBar>,
    pub support_labels: Option<SupportLabelSpec>,
}

/// Layout coordinates for every node, parallel-indexed by [`NodeId`].
#[derive(Debug, Clone, Default)]
pub struct Layout {
    pub x: Vec<f64>,
    pub y: Vec<f64>,
}

impl Layout {
    pub fn len(&self) -> usize {
        self.x.len()
    }

    pub fn is_empty(&self) -> bool {
        self.x.is_empty()
    }

    /// Project to `(name, x, y)` for every named tip, in postorder.
    pub fn tips_by_name(&self, tree: &Tree) -> Vec<(String, f64, f64)> {
        let mut out = Vec::new();
        for id in tree.postorder() {
            if !tree.is_tip[id] || tree.name[id].is_empty() {
                continue;
            }
            out.push((tree.name[id].clone(), self.x[id], self.y[id]));
        }
        out
    }
}

pub fn rectangular_layout(tree: &Tree) -> Layout {
    let n = tree.len();
    let mut layout = Layout {
        x: vec![0.0; n],
        y: vec![0.0; n],
    };

    let Some(root) = tree.root else {
        return layout;
    };

    let preorder = tree.preorder();

    let mut tip_idx = 0_usize;
    for &id in &preorder {
        if tree.is_tip[id] {
            layout.y[id] = tip_idx as f64;
            tip_idx += 1;
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
        let s: f64 = cs.iter().map(|&c| layout.y[c]).sum();
        layout.y[id] = s / cs.len() as f64;
    }

    layout.x[root] = 0.0;
    for &id in &preorder {
        for &c in &tree.children[id] {
            layout.x[c] = layout.x[id] + tree.branch_len[c];
        }
    }

    layout
}

/// Knobs for [`build_rectangular_scene`].
#[derive(Debug, Clone)]
pub struct SceneOptions {
    /// Pixels per unit branch length on the x-axis.
    pub px_per_x: f64,
    /// Pixels per tip on the y-axis.
    pub px_per_y: f64,
    /// Outer padding in pixels.
    pub padding: f64,
    /// Tip label font size in pixels.
    pub font_size: f64,
    /// Average glyph width as a fraction of font size. Only consulted
    /// by the legacy [`monospace_measurer`] fallback. v0.2 callers
    /// should pass a real font measurer to
    /// [`build_rectangular_scene_with_measurer`] (treescape-render
    /// supplies a fontdue-backed one); this field is kept as a knob
    /// for the legacy fallback path.
    pub avg_glyph_width: f64,
    /// Pixels of horizontal gap between a tip's x and the start of its
    /// label.
    pub label_offset: f64,
    /// Branch stroke color.
    pub stroke: Color,
    /// Branch stroke width in pixels.
    pub stroke_width: f64,
    /// Tip label color.
    pub label_color: Color,
}

impl Default for SceneOptions {
    fn default() -> Self {
        Self {
            px_per_x: 60.0,
            px_per_y: 18.0,
            padding: 12.0,
            font_size: 12.0,
            avg_glyph_width: 0.6,
            label_offset: 4.0,
            stroke: Color::black(),
            stroke_width: 1.0,
            label_color: Color::black(),
        }
    }
}

pub fn build_rectangular_scene(tree: &Tree, layout: &Layout, opts: &SceneOptions) -> Scene {
    // Legacy monospace fallback that honors opts.avg_glyph_width.
    // Treats every glyph as fixed-width — wrong for DejaVu Sans, but
    // kept as a font-free path. v0.2 callers go via
    // build_rectangular_scene_with_measurer + a fontdue measurer.
    let agw = opts.avg_glyph_width;
    let measure = move |s: &str, fs: f64| s.chars().count() as f64 * fs * agw;
    build_rectangular_scene_with_measurer(tree, layout, opts, &measure)
}

pub fn build_rectangular_scene_with_measurer(
    tree: &Tree,
    layout: &Layout,
    opts: &SceneOptions,
    measure_width: &dyn Fn(&str, f64) -> f64,
) -> Scene {
    build_rectangular_scene_with_style(tree, layout, opts, measure_width, &StyleSpec::default())
}

/// Like [`build_rectangular_scene`] but takes an explicit text-width
/// measurer **and** a [`StyleSpec`] for clade-highlight rectangles
/// and per-tip color overrides. The measurer is what
/// `treescape-render` injects (fontdue against the bundled font). The
/// styling is what the v0.2 Phase-3 user-facing grammar
/// (`TreePlot.highlight_clade`, `TreePlot.color_tips`) routes through.
///
/// Highlight rectangles are emitted **first** so they render behind
/// branches and labels.
///
/// Backs the `treescape-text-width-vs-fontdue` and
/// `treescape-styling-determinism` EVIDENT claims.
pub fn build_rectangular_scene_with_style(
    tree: &Tree,
    layout: &Layout,
    opts: &SceneOptions,
    measure_width: &dyn Fn(&str, f64) -> f64,
    style: &StyleSpec,
) -> Scene {
    if tree.is_empty() {
        return Scene {
            canvas: Canvas {
                width: 0.0,
                height: 0.0,
            },
            items: Vec::new(),
        };
    }

    // Branch lengths can be negative (legal Newick, see fixture
    // edge/neg_branches.nwk), so cumulative x can be < 0. We must
    // shift the layout so that the leftmost coordinate is at the
    // padding boundary; otherwise nodes render outside the canvas.
    let min_x = layout
        .x
        .iter()
        .cloned()
        .fold(f64::INFINITY, f64::min)
        .min(0.0);
    let max_x = layout.x.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    let max_y = layout.y.iter().cloned().fold(0.0_f64, f64::max);
    let max_label_px = tree
        .name
        .iter()
        .enumerate()
        .filter(|(i, _)| tree.is_tip[*i])
        .map(|(_, n)| measure_width(n, opts.font_size))
        .fold(0.0_f64, f64::max);

    let x_span = (max_x - min_x).max(0.0);
    let scale_bar_extra_h = if style.scale_bar.is_some() {
        opts.font_size * 2.2 + 6.0
    } else {
        0.0
    };
    let scale_bar_width = style
        .scale_bar
        .as_ref()
        .filter(|s| s.length > 0.0)
        .map(|s| opts.padding * 2.0 + s.length * opts.px_per_x)
        .unwrap_or(0.0);
    let content_width =
        opts.padding * 2.0 + x_span * opts.px_per_x + opts.label_offset + max_label_px;
    let canvas = Canvas {
        width: content_width.max(scale_bar_width),
        height: opts.padding * 2.0 + max_y * opts.px_per_y + scale_bar_extra_h,
    };
    // Helper: tree-x -> pixel-x with the negative-cumulative shift baked in.
    let to_px_x = |xv: f64| opts.padding + (xv - min_x) * opts.px_per_x;

    let mut items = Vec::new();

    // Highlight rectangles emitted FIRST so they render behind
    // branches and tip labels.
    for h in &style.highlights {
        let tip_refs: Vec<&str> = h.tip_names.iter().map(String::as_str).collect();
        let mrca = match find_mrca(tree, &tip_refs) {
            Ok(m) => m,
            Err(_) => continue, // empty list / missing tip — skip silently; CLI surface validates upstream
        };
        let tips = clade_tips(tree, mrca);
        if tips.is_empty() {
            continue;
        }
        let tip_ys: Vec<f64> = tips.iter().map(|&i| layout.y[i]).collect();
        let min_ty = tip_ys.iter().cloned().fold(f64::INFINITY, f64::min);
        let max_ty = tip_ys.iter().cloned().fold(f64::NEG_INFINITY, f64::max);

        let half_row = opts.px_per_y * 0.5;
        let rx = to_px_x(layout.x[mrca]);
        let ry = opts.padding + min_ty * opts.px_per_y - half_row;
        let rw = canvas.width - rx - opts.padding;
        let rh = (max_ty - min_ty) * opts.px_per_y + 2.0 * half_row;
        items.push(SceneItem::Rect {
            x: rx,
            y: ry,
            width: rw.max(0.0),
            height: rh.max(0.0),
            fill: h.fill,
        });
    }

    // Branches: for every internal node with children, draw a vertical
    // spine from min child y to max child y at the parent's x, plus a
    // horizontal segment from the parent to each child at the child's y.
    for id in tree.preorder() {
        if tree.children[id].is_empty() {
            continue;
        }
        let parent_px_x = to_px_x(layout.x[id]);
        let child_ys: Vec<f64> = tree.children[id].iter().map(|&c| layout.y[c]).collect();
        let min_cy = child_ys.iter().cloned().fold(f64::INFINITY, f64::min);
        let max_cy = child_ys.iter().cloned().fold(f64::NEG_INFINITY, f64::max);

        items.push(SceneItem::Line {
            x1: parent_px_x,
            y1: opts.padding + min_cy * opts.px_per_y,
            x2: parent_px_x,
            y2: opts.padding + max_cy * opts.px_per_y,
            stroke: opts.stroke,
            stroke_width: opts.stroke_width,
        });

        for &c in &tree.children[id] {
            let child_px_x = to_px_x(layout.x[c]);
            let child_px_y = opts.padding + layout.y[c] * opts.px_per_y;
            let branch_color = style.branch_colors.get(&c).copied().unwrap_or(opts.stroke);
            let branch_width = style
                .branch_widths
                .get(&c)
                .copied()
                .unwrap_or(opts.stroke_width);
            items.push(SceneItem::Line {
                x1: parent_px_x,
                y1: child_px_y,
                x2: child_px_x,
                y2: child_px_y,
                stroke: branch_color,
                stroke_width: branch_width,
            });
        }
    }

    // Tip labels
    for id in tree.preorder() {
        if !tree.is_tip[id] || tree.name[id].is_empty() {
            continue;
        }
        let tx = to_px_x(layout.x[id]) + opts.label_offset;
        let ty = opts.padding + layout.y[id] * opts.px_per_y + opts.font_size * 0.35;
        let label_color = style
            .tip_colors
            .get(&tree.name[id])
            .copied()
            .unwrap_or(opts.label_color);
        items.push(SceneItem::Text {
            x: tx,
            y: ty,
            text: tree.name[id].clone(),
            font_size: opts.font_size,
            color: label_color,
            anchor: TextAnchor::Start,
            is_tip_label: true,
            rotation_deg: 0.0,
        });
    }

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
            items.push(SceneItem::Text {
                x: to_px_x(layout.x[id]) + opts.label_offset,
                y: opts.padding + layout.y[id] * opts.px_per_y - opts.font_size * 0.25,
                text: tree.name[id].clone(),
                font_size: opts.font_size,
                color: opts.label_color,
                anchor: TextAnchor::Start,
                is_tip_label: false,
                rotation_deg: 0.0,
            });
        }
    }

    if let Some(scale_bar) = &style.scale_bar {
        if scale_bar.length > 0.0 {
            let bar_x1 = opts.padding;
            let bar_x2 = bar_x1 + scale_bar.length * opts.px_per_x;
            let bar_y = opts.padding + max_y * opts.px_per_y + opts.font_size * 0.8;
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

    Scene { canvas, items }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::newick::parse;

    fn approx(a: f64, b: f64) -> bool {
        (a - b).abs() < 1e-12
    }

    #[test]
    fn balanced_4_known_coords() {
        let t = parse("((a:1.0,b:1.0):1.0,(c:1.0,d:1.0):1.0);").unwrap();
        let l = rectangular_layout(&t);
        let tips = l.tips_by_name(&t);
        let map: std::collections::HashMap<_, _> =
            tips.iter().map(|(n, x, y)| (n.clone(), (*x, *y))).collect();
        assert!(approx(map["a"].0, 2.0) && approx(map["a"].1, 0.0));
        assert!(approx(map["b"].0, 2.0) && approx(map["b"].1, 1.0));
        assert!(approx(map["c"].0, 2.0) && approx(map["c"].1, 2.0));
        assert!(approx(map["d"].0, 2.0) && approx(map["d"].1, 3.0));
        assert!(approx(l.y[t.root.unwrap()], 1.5));
        assert!(approx(l.x[t.root.unwrap()], 0.0));
    }

    #[test]
    fn two_tip_known_coords() {
        let t = parse("(a:1.0,b:2.0);").unwrap();
        let l = rectangular_layout(&t);
        let tips = l.tips_by_name(&t);
        let map: std::collections::HashMap<_, _> =
            tips.iter().map(|(n, x, y)| (n.clone(), (*x, *y))).collect();
        assert!(approx(map["a"].0, 1.0) && approx(map["a"].1, 0.0));
        assert!(approx(map["b"].0, 2.0) && approx(map["b"].1, 1.0));
    }

    #[test]
    fn unbalanced_5_known_coords() {
        let t = parse("((((a:1.0,b:1.0):1.0,c:2.0):1.0,d:3.0):1.0,e:4.0);").unwrap();
        let l = rectangular_layout(&t);
        let tips = l.tips_by_name(&t);
        let map: std::collections::HashMap<_, _> =
            tips.iter().map(|(n, x, y)| (n.clone(), (*x, *y))).collect();
        for tip in ["a", "b", "c", "d", "e"] {
            assert!(approx(map[tip].0, 4.0), "{} x: {}", tip, map[tip].0);
        }
        assert!(approx(map["a"].1, 0.0));
        assert!(approx(map["b"].1, 1.0));
        assert!(approx(map["c"].1, 2.0));
        assert!(approx(map["d"].1, 3.0));
        assert!(approx(map["e"].1, 4.0));
    }

    #[test]
    fn negative_branch_propagates() {
        let t = parse("(a:-0.1,b:0.5);").unwrap();
        let l = rectangular_layout(&t);
        let tips = l.tips_by_name(&t);
        let map: std::collections::HashMap<_, _> =
            tips.iter().map(|(n, x, y)| (n.clone(), (*x, *y))).collect();
        assert!(approx(map["a"].0, -0.1));
        assert!(approx(map["b"].0, 0.5));
    }

    #[test]
    fn trifurcation_root() {
        let t = parse("(a:1.0,b:1.0,c:1.0);").unwrap();
        let l = rectangular_layout(&t);
        let tips = l.tips_by_name(&t);
        let map: std::collections::HashMap<_, _> =
            tips.iter().map(|(n, x, y)| (n.clone(), (*x, *y))).collect();
        assert!(approx(map["a"].1, 0.0));
        assert!(approx(map["b"].1, 1.0));
        assert!(approx(map["c"].1, 2.0));
        assert!(approx(l.y[t.root.unwrap()], 1.0));
    }

    #[test]
    fn scene_tip_count_matches() {
        let t = parse("((a:1.0,b:1.0):1.0,(c:1.0,d:1.0):1.0);").unwrap();
        let l = rectangular_layout(&t);
        let s = build_rectangular_scene(&t, &l, &SceneOptions::default());
        assert_eq!(s.count_tip_labels(), 4);
    }

    #[test]
    fn scene_coords_within_canvas() {
        let t = parse("((((a:1.0,b:1.0):1.0,c:2.0):1.0,d:3.0):1.0,e:4.0);").unwrap();
        let l = rectangular_layout(&t);
        let s = build_rectangular_scene(&t, &l, &SceneOptions::default());
        assert!(s.coords_within_canvas(1e-6));
    }

    #[test]
    fn scene_coords_within_canvas_negative_branch() {
        // Negative branch lengths produce negative cumulative x. Without
        // the min_x shift, tips render at negative pixel coords outside
        // the canvas.
        let t = parse("(a:-0.5,b:0.5);").unwrap();
        let l = rectangular_layout(&t);
        let s = build_rectangular_scene(&t, &l, &SceneOptions::default());
        assert!(
            s.coords_within_canvas(1e-6),
            "negative branch leaks coords outside canvas"
        );
    }

    #[test]
    fn scene_is_deterministic() {
        // Same input -> identical Scene structure (we can't compare the
        // enum directly, so check item count + a few fields).
        let t = parse("((a:1.0,b:1.0):1.0,(c:1.0,d:1.0):1.0);").unwrap();
        let l = rectangular_layout(&t);
        let s1 = build_rectangular_scene(&t, &l, &SceneOptions::default());
        let s2 = build_rectangular_scene(&t, &l, &SceneOptions::default());
        assert_eq!(s1.items.len(), s2.items.len());
        assert_eq!(s1.canvas.width, s2.canvas.width);
        assert_eq!(s1.canvas.height, s2.canvas.height);
    }

    #[test]
    fn scale_bar_adds_non_tip_label_and_extra_height() {
        let t = parse("(a:1.0,b:2.0);").unwrap();
        let l = rectangular_layout(&t);
        let opts = SceneOptions::default();
        let base = build_rectangular_scene(&t, &l, &opts);
        let style = StyleSpec {
            scale_bar: Some(ScaleBar {
                length: 0.5,
                label: "0.5".to_string(),
            }),
            ..StyleSpec::default()
        };
        let with_bar = build_rectangular_scene_with_style(
            &t,
            &l,
            &opts,
            &|s, fs| s.chars().count() as f64 * fs * 0.6,
            &style,
        );
        assert!(with_bar.canvas.height > base.canvas.height);
        assert_eq!(with_bar.count_tip_labels(), 2);
        assert!(with_bar.items.iter().any(|item| {
            matches!(
                item,
                SceneItem::Text {
                    text,
                    is_tip_label: false,
                    ..
                } if text == "0.5"
            )
        }));
        assert!(with_bar.coords_within_canvas(1e-6));
    }

    #[test]
    fn support_labels_render_internal_names_only_when_enabled() {
        let t = parse("((a:1.0,b:1.0)95:0.2,c:1.0)root;").unwrap();
        let l = rectangular_layout(&t);
        let opts = SceneOptions::default();
        let base = build_rectangular_scene(&t, &l, &opts);
        assert_eq!(base.count_tip_labels(), 3);
        assert!(!base.items.iter().any(|item| {
            matches!(
                item,
                SceneItem::Text {
                    text,
                    is_tip_label: false,
                    ..
                } if text == "95"
            )
        }));

        let style = StyleSpec {
            support_labels: Some(SupportLabelSpec::default()),
            ..StyleSpec::default()
        };
        let with_support = build_rectangular_scene_with_style(
            &t,
            &l,
            &opts,
            &|s, fs| s.chars().count() as f64 * fs * 0.6,
            &style,
        );
        assert_eq!(with_support.count_tip_labels(), 3);
        assert!(with_support.items.iter().any(|item| {
            matches!(
                item,
                SceneItem::Text {
                    text,
                    is_tip_label: false,
                    ..
                } if text == "95"
            )
        }));
    }

    #[test]
    fn support_labels_can_filter_numeric_values() {
        let t = parse("((a:1.0,b:1.0)65:0.2,(c:1.0,d:1.0)95:0.2);").unwrap();
        let l = rectangular_layout(&t);
        let opts = SceneOptions::default();
        let style = StyleSpec {
            support_labels: Some(SupportLabelSpec {
                min_value: Some(70.0),
            }),
            ..StyleSpec::default()
        };
        let scene = build_rectangular_scene_with_style(
            &t,
            &l,
            &opts,
            &|s, fs| s.chars().count() as f64 * fs * 0.6,
            &style,
        );
        assert!(scene.items.iter().any(|item| {
            matches!(
                item,
                SceneItem::Text {
                    text,
                    is_tip_label: false,
                    ..
                } if text == "95"
            )
        }));
        assert!(!scene.items.iter().any(|item| {
            matches!(
                item,
                SceneItem::Text {
                    text,
                    is_tip_label: false,
                    ..
                } if text == "65"
            )
        }));
    }

    #[test]
    fn branch_color_overrides_horizontal_branch_to_child_node() {
        let t = parse("((a:1.0,b:1.0):1.0,c:2.0);").unwrap();
        let l = rectangular_layout(&t);
        let child = t.children[t.root.unwrap()][0];
        let style = StyleSpec {
            branch_colors: HashMap::from([(child, Color::rgb(255, 0, 0))]),
            ..StyleSpec::default()
        };
        let scene = build_rectangular_scene_with_style(
            &t,
            &l,
            &SceneOptions::default(),
            &|s, fs| s.chars().count() as f64 * fs * 0.6,
            &style,
        );

        assert!(scene.items.iter().any(|item| {
            matches!(
                item,
                SceneItem::Line {
                    stroke,
                    ..
                } if *stroke == Color::rgb(255, 0, 0)
            )
        }));
    }
}
