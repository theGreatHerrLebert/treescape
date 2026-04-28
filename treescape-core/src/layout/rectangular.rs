//! Rectangular phylogram layout.
//!
//! Conventions are owned by the Python reference at
//! `packages/treescape-reference/src/treescape_reference/layout.py`
//! and documented in `docs/conventions.md`. This module is a port of
//! that reference; agreement within `1e-9` is pinned by the EVIDENT
//! claim `treescape-layout-rust-vs-reference` and is verified
//! end-to-end once the PyO3 connector lands in Phase 4.
//!
//! Algorithm:
//! 1. Pre-order pass to assign tip y as 0, 1, ..., N-1.
//! 2. Post-order pass to fill internal y as the arithmetic mean of
//!    immediate children's y.
//! 3. Pre-order pass to fill x = parent.x + child.branch_len; root x = 0.

use crate::tree::{NodeId, Tree};

/// Result of a layout pass — parallel arrays indexed by [`NodeId`].
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

    /// Project to `{tip_name -> (x, y)}`. Skips empty names.
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::newick::parse;

    fn approx(a: f64, b: f64) -> bool {
        (a - b).abs() < 1e-12
    }

    #[test]
    fn balanced_4_known_coords() {
        // ((a:1,b:1):1,(c:1,d:1):1);
        // Expected:
        //   root          x=0    y=1.5
        //   (a,b) clade   x=1    y=0.5
        //     a           x=2    y=0
        //     b           x=2    y=1
        //   (c,d) clade   x=1    y=2.5
        //     c           x=2    y=2
        //     d           x=2    y=3
        let t = parse("((a:1.0,b:1.0):1.0,(c:1.0,d:1.0):1.0);").unwrap();
        let l = rectangular_layout(&t);
        let tips = l.tips_by_name(&t);
        let map: std::collections::HashMap<_, _> =
            tips.iter().map(|(n, x, y)| (n.clone(), (*x, *y))).collect();
        assert!(approx(map["a"].0, 2.0) && approx(map["a"].1, 0.0));
        assert!(approx(map["b"].0, 2.0) && approx(map["b"].1, 1.0));
        assert!(approx(map["c"].0, 2.0) && approx(map["c"].1, 2.0));
        assert!(approx(map["d"].0, 2.0) && approx(map["d"].1, 3.0));
        // Root y is the mean of internal children y (0.5 and 2.5)
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
        // ((((a:1,b:1):1,c:2):1,d:3):1,e:4);
        let t = parse("((((a:1.0,b:1.0):1.0,c:2.0):1.0,d:3.0):1.0,e:4.0);").unwrap();
        let l = rectangular_layout(&t);
        let tips = l.tips_by_name(&t);
        let map: std::collections::HashMap<_, _> =
            tips.iter().map(|(n, x, y)| (n.clone(), (*x, *y))).collect();
        // All tips at the same x (sum of root-to-tip branch lengths) by construction
        // a: 1+1+1+1=4, b: 1+1+1+1=4, c: 1+1+2=4, d: 1+3=4, e: 4
        for tip in ["a", "b", "c", "d", "e"] {
            assert!(approx(map[tip].0, 4.0), "{} x mismatch: {}", tip, map[tip].0);
        }
        // Tip y in preorder of leaves: a=0, b=1, c=2, d=3, e=4
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
        // Root y = mean of three children y = (0+1+2)/3 = 1.0
        assert!(approx(l.y[t.root.unwrap()], 1.0));
    }
}
