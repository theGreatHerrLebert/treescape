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
pub fn circular_layout_with(
    tree: &Tree,
    start_angle: f64,
    sweep_total: f64,
) -> CircularLayout {
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

    let tips: Vec<usize> = preorder.iter().copied().filter(|&i| tree.is_tip[i]).collect();
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
