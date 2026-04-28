//! Ladderization.
//!
//! Reorders children at every internal node by subtree size. Tie-break
//! rules (matched against ete3 — see docs/conventions.md):
//!
//! * **Ascending** (`ascending=true`, ete3 `direction=0`): stable sort
//!   by subtree size ascending. Ties preserve original child order.
//!
//! * **Descending** (`ascending=false`, ete3 `direction=1`): sort by
//!   `(Reverse(size), Reverse(original_position))`. Ties have their
//!   original order *reversed*. This matches ete3 exactly on every
//!   canonical fixture and is the documented behavior for the
//!   `treescape-ladderize-order` claim.

use crate::tree::{NodeId, Tree};

pub fn ladderize(tree: &mut Tree, ascending: bool) {
    if tree.root.is_none() {
        return;
    }

    let n = tree.len();
    let mut sizes = vec![0_usize; n];
    for id in tree.postorder() {
        if tree.children[id].is_empty() {
            sizes[id] = 1;
        } else {
            sizes[id] = tree.children[id].iter().map(|&c| sizes[c]).sum();
        }
    }

    for id in 0..n {
        if tree.children[id].is_empty() {
            continue;
        }
        if ascending {
            tree.children[id].sort_by_key(|&c| sizes[c]);
        } else {
            // Match ete3 direction=1: ties have original order reversed.
            // Achieved by sorting on (Reverse(size), Reverse(original_pos)).
            let indexed: Vec<(usize, NodeId)> =
                tree.children[id].iter().copied().enumerate().collect();
            let mut keyed: Vec<(usize, usize, NodeId)> = indexed
                .into_iter()
                .map(|(orig_pos, c)| (sizes[c], orig_pos, c))
                .collect();
            keyed.sort_by(|a, b| b.0.cmp(&a.0).then_with(|| b.1.cmp(&a.1)));
            tree.children[id] = keyed.into_iter().map(|(_, _, c)| c).collect();
        }
    }
}

/// Tip names in pre-order traversal — the visible top-to-bottom order
/// after ladderization.
pub fn tip_order(tree: &Tree) -> Vec<String> {
    let mut out = Vec::new();
    for id in tree.preorder() {
        if tree.is_tip[id] {
            out.push(tree.name[id].clone());
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::newick::parse;

    #[test]
    fn ladderize_unbalanced() {
        // Pre-ladderize tip order: a, b, c, d, e
        let mut t = parse("((((a:1.0,b:1.0):1.0,c:2.0):1.0,d:3.0):1.0,e:4.0);").unwrap();
        let before = tip_order(&t);
        assert_eq!(before, vec!["a", "b", "c", "d", "e"]);

        ladderize(&mut t, true);
        let after = tip_order(&t);
        // Smallest subtrees come first: e (size 1) ahead of the rest at the root,
        // d (size 1) ahead of the larger subtree, ...
        // root children: [(((a,b),c),d) size 4, e size 1] -> ascending puts e first
        // (((a,b),c),d) children: [((a,b),c) size 3, d size 1] -> [d, ((a,b),c)]
        // ((a,b),c) children: [(a,b) size 2, c size 1] -> [c, (a,b)]
        // (a,b) children: [a size 1, b size 1] -> tie, preserve [a, b]
        // So tip order: e, d, c, a, b
        assert_eq!(after, vec!["e", "d", "c", "a", "b"]);
    }

    #[test]
    fn ladderize_descending_matches_ete3() {
        // Ete3 direction=1 reverses tied groups. (b,c) is tied size 1 each,
        // so under desc the (b,c) siblings flip to (c,b).
        // Root children [(a,(b,c)) size 3, d size 1] desc -> [(a,(b,c)), d]
        // (a, (b,c)) children: [a size 1, (b,c) size 2] desc -> [(b,c), a]
        // (b,c) children: [b, c] tied size 1 desc -> [c, b]
        let mut t = parse("((a:1.0,(b:1.0,c:1.0):1.0):1.0,d:1.0);").unwrap();
        ladderize(&mut t, false);
        let order = tip_order(&t);
        assert_eq!(order, vec!["c", "b", "a", "d"]);
    }

    #[test]
    fn ladderize_asc_preserves_ties() {
        // balanced: ((a,b):1,(c,d):1)
        // root: two subtrees of size 2 each -> tie under asc, preserve [(a,b),(c,d)]
        let mut t = parse("((a:1.0,b:1.0):1.0,(c:1.0,d:1.0):1.0);").unwrap();
        ladderize(&mut t, true);
        let order = tip_order(&t);
        assert_eq!(order, vec!["a", "b", "c", "d"]);
    }

    #[test]
    fn ladderize_desc_reverses_ties_at_root() {
        // balanced root has two subtrees of size 2 each -> tie under desc, REVERSE
        // [(a,b),(c,d)] desc -> [(c,d),(a,b)]
        // Each sub-(x,y) has tied tips -> [d,c] and [b,a]
        let mut t = parse("((a:1.0,b:1.0):1.0,(c:1.0,d:1.0):1.0);").unwrap();
        ladderize(&mut t, false);
        let order = tip_order(&t);
        assert_eq!(order, vec!["d", "c", "b", "a"]);
    }
}
