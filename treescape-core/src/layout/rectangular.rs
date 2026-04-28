//! Rectangular phylogram layout + scene construction.
//!
//! Conventions are owned by the Python reference at
//! `packages/treescape-reference/src/treescape_reference/layout.py`
//! and documented in `docs/conventions.md`.

use crate::layout::scene::{Canvas, Color, Scene, SceneItem, TextAnchor};
use crate::tree::Tree;

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
    /// Approximate average glyph width as a fraction of font size.
    /// Used to size the canvas for tip labels. v0.1 ships a
    /// monospace-like 0.6 default; v0.2 will swap in fontdue-measured
    /// widths.
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

pub fn build_rectangular_scene(
    tree: &Tree,
    layout: &Layout,
    opts: &SceneOptions,
) -> Scene {
    if tree.is_empty() {
        return Scene {
            canvas: Canvas { width: 0.0, height: 0.0 },
            items: Vec::new(),
        };
    }

    let max_x = layout.x.iter().cloned().fold(0.0_f64, f64::max);
    let max_y = layout.y.iter().cloned().fold(0.0_f64, f64::max);
    let max_label_chars = tree
        .name
        .iter()
        .enumerate()
        .filter(|(i, _)| tree.is_tip[*i])
        .map(|(_, n)| n.chars().count())
        .max()
        .unwrap_or(0);
    let max_label_px =
        (max_label_chars as f64) * opts.font_size * opts.avg_glyph_width;

    let canvas = Canvas {
        width: opts.padding * 2.0 + max_x * opts.px_per_x + opts.label_offset + max_label_px,
        height: opts.padding * 2.0 + max_y * opts.px_per_y,
    };

    let mut items = Vec::new();

    // Branches: for every internal node with children, draw a vertical
    // spine from min child y to max child y at the parent's x, plus a
    // horizontal segment from the parent to each child at the child's y.
    for id in tree.preorder() {
        if tree.children[id].is_empty() {
            continue;
        }
        let parent_px_x = opts.padding + layout.x[id] * opts.px_per_x;
        let child_ys: Vec<f64> = tree.children[id]
            .iter()
            .map(|&c| layout.y[c])
            .collect();
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
            let child_px_x = opts.padding + layout.x[c] * opts.px_per_x;
            let child_px_y = opts.padding + layout.y[c] * opts.px_per_y;
            items.push(SceneItem::Line {
                x1: parent_px_x,
                y1: child_px_y,
                x2: child_px_x,
                y2: child_px_y,
                stroke: opts.stroke,
                stroke_width: opts.stroke_width,
            });
        }
    }

    // Tip labels
    for id in tree.preorder() {
        if !tree.is_tip[id] || tree.name[id].is_empty() {
            continue;
        }
        let tx = opts.padding + layout.x[id] * opts.px_per_x + opts.label_offset;
        let ty = opts.padding + layout.y[id] * opts.px_per_y + opts.font_size * 0.35;
        items.push(SceneItem::Text {
            x: tx,
            y: ty,
            text: tree.name[id].clone(),
            font_size: opts.font_size,
            color: opts.label_color,
            anchor: TextAnchor::Start,
            is_tip_label: true,
        });
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
}
