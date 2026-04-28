//! Clade utilities: MRCA, clade-tip enumeration.
//!
//! Used by the Phase-3 styling pipeline (clade highlighting) to
//! resolve a tip-name list to a subtree. Mirrors the Python reference
//! at `packages/treescape-reference/.../layout.py::find_mrca`.

use std::collections::HashSet;

use crate::tree::Tree;

/// Most-recent-common-ancestor node id of the given tip names.
///
/// Returns `Err(name)` for the first missing tip; `Err("")` if the
/// list is empty or the tree has no root.
pub fn find_mrca(tree: &Tree, tip_names: &[&str]) -> Result<usize, String> {
    if tip_names.is_empty() {
        return Err(String::from(""));
    }
    let Some(root) = tree.root else {
        return Err(String::from(""));
    };

    let mut node_for: Vec<usize> = Vec::with_capacity(tip_names.len());
    for &want in tip_names {
        let mut found: Option<usize> = None;
        for id in 0..tree.len() {
            if tree.is_tip[id] && tree.name[id] == want {
                found = Some(id);
                break;
            }
        }
        match found {
            Some(id) => node_for.push(id),
            None => return Err(want.to_string()),
        }
    }

    if node_for.len() == 1 {
        return Ok(node_for[0]);
    }

    let mut parent_of: Vec<Option<usize>> = vec![None; tree.len()];
    for id in 0..tree.len() {
        for &c in &tree.children[id] {
            parent_of[c] = Some(id);
        }
    }

    let ancestors_of = |start: usize| -> Vec<usize> {
        let mut out = vec![start];
        let mut cur = start;
        while let Some(p) = parent_of[cur] {
            out.push(p);
            cur = p;
        }
        out
    };

    let mut common: HashSet<usize> = ancestors_of(node_for[0]).into_iter().collect();
    for &nf in &node_for[1..] {
        let anc: HashSet<usize> = ancestors_of(nf).into_iter().collect();
        common = common.intersection(&anc).copied().collect();
    }

    for a in ancestors_of(node_for[0]) {
        if common.contains(&a) {
            return Ok(a);
        }
    }
    // Unreachable for a connected tree but keep the compiler happy.
    let _ = root;
    Err(String::from(""))
}

/// All tips in the subtree rooted at `mrca`, in pre-order.
pub fn clade_tips(tree: &Tree, mrca: usize) -> Vec<usize> {
    if tree.is_tip[mrca] {
        return vec![mrca];
    }
    let mut out = Vec::new();
    let mut stack = vec![mrca];
    while let Some(n) = stack.pop() {
        if tree.is_tip[n] {
            out.push(n);
        }
        for &c in tree.children[n].iter().rev() {
            stack.push(c);
        }
    }
    // Stack-pop order yields visit order; for pre-order we want
    // first-child-first which the rev() above achieves.
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::newick::parse;

    #[test]
    fn mrca_pair() {
        let t = parse("((((a:1,b:1):1,c:2):1,d:3):1,e:4);").unwrap();
        let m = find_mrca(&t, &["a", "b"]).unwrap();
        let names: Vec<&str> = clade_tips(&t, m)
            .iter()
            .map(|&i| t.name[i].as_str())
            .collect();
        assert_eq!(names, vec!["a", "b"]);
    }

    #[test]
    fn mrca_separate_clades() {
        let t = parse("((((a:1,b:1):1,c:2):1,d:3):1,e:4);").unwrap();
        let m = find_mrca(&t, &["a", "d"]).unwrap();
        let names: Vec<&str> = clade_tips(&t, m)
            .iter()
            .map(|&i| t.name[i].as_str())
            .collect();
        assert_eq!(names, vec!["a", "b", "c", "d"]);
    }

    #[test]
    fn mrca_single_tip_is_self() {
        let t = parse("(a:1,b:1);").unwrap();
        let m = find_mrca(&t, &["a"]).unwrap();
        assert!(t.is_tip[m]);
        assert_eq!(t.name[m], "a");
    }

    #[test]
    fn mrca_missing_tip_errors() {
        let t = parse("(a:1,b:1);").unwrap();
        assert!(find_mrca(&t, &["x"]).is_err());
    }

    #[test]
    fn mrca_root_when_disjoint_clades() {
        let t = parse("((a:1,b:1):1,(c:1,d:1):1);").unwrap();
        let m = find_mrca(&t, &["a", "d"]).unwrap();
        assert_eq!(m, t.root.unwrap());
    }
}
