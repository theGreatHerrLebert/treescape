//! Struct-of-arrays Tree representation.
//!
//! Decided in plan: parallel `Vec<usize> parent_idx`, `Vec<f64> branch_len`,
//! `Vec<String> name`, `Vec<bool> is_tip`, `Vec<Option<u32>> meta_idx`.
//! Index-based API. Do not switch to `Vec<Node>` — see CLAUDE.md.

#![allow(dead_code)]

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
}
