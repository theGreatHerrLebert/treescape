//! Struct-of-arrays Tree representation.
//!
//! Parallel arrays indexed by [`NodeId`]. The plan pinned this shape;
//! see CLAUDE.md for why an arena `Vec<Node>` is the wrong choice here.
//!
//! Branch lengths are `f64` with a `0.0` default. "No branch length
//! specified" and "branch length 0.0" are not distinguished; this is a
//! deliberate v0.1 simplification documented in evident.yaml's
//! `treescape-newick-roundtrip` claim.

#![allow(dead_code)]

use std::hash::{Hash, Hasher};

pub type NodeId = usize;

#[derive(Debug, Clone, Default)]
pub struct Tree {
    pub parent: Vec<Option<NodeId>>,
    pub children: Vec<Vec<NodeId>>,
    pub branch_len: Vec<f64>,
    pub name: Vec<String>,
    pub is_tip: Vec<bool>,
    pub meta_idx: Vec<Option<u32>>,
    pub root: Option<NodeId>,
}

impl Tree {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn len(&self) -> usize {
        self.parent.len()
    }

    pub fn is_empty(&self) -> bool {
        self.parent.is_empty()
    }

    pub fn add_node(&mut self) -> NodeId {
        let id = self.parent.len();
        self.parent.push(None);
        self.children.push(Vec::new());
        self.branch_len.push(0.0);
        self.name.push(String::new());
        self.is_tip.push(false);
        self.meta_idx.push(None);
        id
    }

    /// Recompute is_tip flags from the children arrays. Call after the
    /// structure is fully built.
    pub fn finalize(&mut self) {
        for i in 0..self.len() {
            self.is_tip[i] = self.children[i].is_empty();
        }
    }

    /// Iterative postorder (children before parents). Empty tree returns empty.
    pub fn postorder(&self) -> Vec<NodeId> {
        let mut out = Vec::with_capacity(self.len());
        let Some(root) = self.root else {
            return out;
        };
        let mut stack = vec![root];
        while let Some(id) = stack.pop() {
            out.push(id);
            for &c in &self.children[id] {
                stack.push(c);
            }
        }
        out.reverse();
        out
    }

    /// Order-invariant Merkle-style hash of structure + names.
    /// Branch lengths are intentionally excluded — they have their
    /// own comparison in the round-trip claim.
    pub fn topology_hash(&self) -> u64 {
        let mut node_hash: Vec<u64> = vec![0; self.len()];
        for id in self.postorder() {
            let mut hasher = fxhash::FxHasher::default();
            self.name[id].hash(&mut hasher);
            let mut child_h: Vec<u64> = self.children[id]
                .iter()
                .map(|&c| node_hash[c])
                .collect();
            child_h.sort_unstable();
            for h in &child_h {
                h.hash(&mut hasher);
            }
            node_hash[id] = hasher.finish();
        }
        match self.root {
            Some(r) => node_hash[r],
            None => 0,
        }
    }
}
