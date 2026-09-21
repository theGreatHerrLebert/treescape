//! treescape-core: tree model, parsers, traversal, layout, scene graph.
//!
//! Pure Rust, no host bindings. `evident.yaml` at the workspace root is
//! the trust manifest that gates what ships; `docs/conventions.md` pins
//! every convention the code follows.

pub mod clades;
pub mod ladderize;
pub mod layout;
pub mod newick;
pub mod seq_distance;
pub mod style;
pub mod traversal;
pub mod tree;
pub mod tree_build;
