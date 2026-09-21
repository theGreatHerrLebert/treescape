//! Tree handle: parse, inspect, free.

use std::ffi::c_char;

use treescape_core::ladderize::tip_order;
use treescape_core::newick;
use treescape_core::tree::Tree;
use treescape_core::tree_build;

use crate::ffi::{
    copy_out, finish, handle, slice_arg, str_arg, write_out, write_string, Failure, FfiResult,
};
use crate::TS_PARSE_ERROR;

/// Largest Newick input accepted (16 MiB; ~500k tips of typical Newick).
/// Parsing costs ~30x the input on typical trees and up to ~160x in the
/// worst case (every byte opens a node), so this caps the parse near
/// 2.7 GB. The parser's large buffers grow fallibly (an out-of-memory
/// parse is an error, not an abort); per-node allocations do not, so the
/// cap keeps them far from memory exhaustion rather than ruling it out.
pub const MAX_NEWICK_BYTES: usize = 16 * 1024 * 1024;

/// Opaque tree handle.
pub struct TsTree {
    pub(crate) tree: Tree,
    /// Tip names in tip order, cached for `ts_tree_tip_name`.
    pub(crate) tips: Vec<String>,
}

impl TsTree {
    pub(crate) fn check_node(&self, id: usize) -> FfiResult<()> {
        if id < self.tree.len() {
            Ok(())
        } else {
            Err(Failure::invalid(format!("node id {id} out of range")))
        }
    }
}

#[no_mangle]
pub extern "C" fn ts_tree_parse_newick(
    src: *const c_char,
    out_tree: *mut *mut TsTree,
    err: *mut *mut c_char,
) -> i32 {
    let run = || -> FfiResult<()> {
        let src = str_arg(src, "src")?;
        if src.len() > MAX_NEWICK_BYTES {
            return Err(Failure::invalid(format!(
                "Newick input is {} bytes; the limit is {MAX_NEWICK_BYTES}",
                src.len()
            )));
        }
        let tree = newick::parse(src).map_err(|e| Failure::new(TS_PARSE_ERROR, e.to_string()))?;
        let tips = tip_order(&tree);
        let boxed = Box::into_raw(Box::new(TsTree { tree, tips }));
        if let Err(f) = write_out(out_tree, boxed, "out_tree") {
            // SAFETY: `boxed` was just created and never shared.
            drop(unsafe { Box::from_raw(boxed) });
            return Err(f);
        }
        Ok(())
    };
    finish(run(), err)
}

/// Largest distance matrix accepted (taxa). Building copies the matrix
/// (8·n² bytes, 800 MB at the limit) and allocation failure aborts the
/// host, so larger inputs are rejected up front.
pub const MAX_TAXA: usize = 10_000;

fn box_tree(tree: Tree, out_tree: *mut *mut TsTree) -> FfiResult<()> {
    let tips = tip_order(&tree);
    let boxed = Box::into_raw(Box::new(TsTree { tree, tips }));
    if let Err(f) = write_out(out_tree, boxed, "out_tree") {
        // SAFETY: `boxed` was just created and never shared.
        drop(unsafe { Box::from_raw(boxed) });
        return Err(f);
    }
    Ok(())
}

fn labels_arg(labels: *const *const c_char, n: usize) -> FfiResult<Vec<String>> {
    slice_arg(labels, n, "labels")?
        .iter()
        .map(|&p| str_arg(p, "label").map(str::to_owned))
        .collect()
}

/// Build a tree from a row-major `n × n` distance matrix. `method`:
/// 0 = neighbor joining, 1 = UPGMA. Invalid input (docs/conventions.md,
/// "Trees from distance matrices") is status 1 with the offending cell.
#[no_mangle]
pub extern "C" fn ts_tree_from_distances(
    matrix: *const f64,
    n: usize,
    labels: *const *const c_char,
    method: u32,
    out_tree: *mut *mut TsTree,
    err: *mut *mut c_char,
) -> i32 {
    let run = || -> FfiResult<()> {
        if n > MAX_TAXA {
            return Err(Failure::invalid(format!(
                "{n} taxa; the limit is {MAX_TAXA}"
            )));
        }
        let cells = n
            .checked_mul(n)
            .ok_or_else(|| Failure::invalid("matrix size overflows"))?;
        let matrix = slice_arg(matrix, cells, "matrix")?;
        let labels = labels_arg(labels, n)?;
        let labels: Vec<&str> = labels.iter().map(String::as_str).collect();
        let tree = match method {
            0 => tree_build::neighbor_joining(matrix, &labels),
            1 => tree_build::upgma(matrix, &labels),
            other => {
                return Err(Failure::invalid(format!(
                    "method must be 0 (nj) or 1 (upgma), got {other}"
                )))
            }
        }
        .map_err(|e| Failure::invalid(e.to_string()))?;
        box_tree(tree, out_tree)
    };
    finish(run(), err)
}

/// Build a tree from a row-major SciPy-style linkage matrix (`n − 1` rows
/// of 4 values) and `n` labels.
#[no_mangle]
pub extern "C" fn ts_tree_from_linkage(
    linkage: *const f64,
    n: usize,
    labels: *const *const c_char,
    out_tree: *mut *mut TsTree,
    err: *mut *mut c_char,
) -> i32 {
    let run = || -> FfiResult<()> {
        if n > MAX_TAXA {
            return Err(Failure::invalid(format!(
                "{n} taxa; the limit is {MAX_TAXA}"
            )));
        }
        let cells = n
            .saturating_sub(1)
            .checked_mul(4)
            .ok_or_else(|| Failure::invalid("linkage size overflows"))?;
        let linkage = slice_arg(linkage, cells, "linkage")?;
        let labels = labels_arg(labels, n)?;
        let labels: Vec<&str> = labels.iter().map(String::as_str).collect();
        let tree = tree_build::from_linkage(linkage, &labels)
            .map_err(|e| Failure::invalid(e.to_string()))?;
        box_tree(tree, out_tree)
    };
    finish(run(), err)
}

/// Release a tree. Null is a no-op.
#[no_mangle]
pub extern "C" fn ts_tree_free(tree: *mut TsTree) {
    if !tree.is_null() {
        // SAFETY: came from `Box::into_raw` in `ts_tree_parse_newick`.
        drop(unsafe { Box::from_raw(tree) });
    }
}

#[no_mangle]
pub extern "C" fn ts_tree_n_nodes(
    tree: *const TsTree,
    out: *mut usize,
    err: *mut *mut c_char,
) -> i32 {
    let run = || write_out(out, handle(tree, "tree")?.tree.len(), "out");
    finish(run(), err)
}

#[no_mangle]
pub extern "C" fn ts_tree_n_tips(
    tree: *const TsTree,
    out: *mut usize,
    err: *mut *mut c_char,
) -> i32 {
    let run = || write_out(out, handle(tree, "tree")?.tips.len(), "out");
    finish(run(), err)
}

/// Root node id; an error for an empty tree.
#[no_mangle]
pub extern "C" fn ts_tree_root(tree: *const TsTree, out: *mut usize, err: *mut *mut c_char) -> i32 {
    let run = || {
        let root = handle(tree, "tree")?
            .tree
            .root
            .ok_or_else(|| Failure::invalid("tree has no root"))?;
        write_out(out, root, "out")
    };
    finish(run(), err)
}

/// Preorder node ids into `buf` (capacity `cap`); count to `out_len`.
#[no_mangle]
pub extern "C" fn ts_tree_preorder(
    tree: *const TsTree,
    buf: *mut usize,
    cap: usize,
    out_len: *mut usize,
    err: *mut *mut c_char,
) -> i32 {
    let run = || {
        let order = handle(tree, "tree")?.tree.preorder();
        if cap < order.len() {
            return Err(Failure::invalid(format!(
                "buffer holds {cap} ids but preorder has {}",
                order.len()
            )));
        }
        copy_out(buf, &order, "buf")?;
        write_out(out_len, order.len(), "out_len")
    };
    finish(run(), err)
}

#[no_mangle]
pub extern "C" fn ts_tree_is_tip(
    tree: *const TsTree,
    node: usize,
    out: *mut u8,
    err: *mut *mut c_char,
) -> i32 {
    let run = || {
        let t = handle(tree, "tree")?;
        t.check_node(node)?;
        let is_tip = t.tree.is_tip.get(node).copied().unwrap_or(false);
        write_out(out, u8::from(is_tip), "out")
    };
    finish(run(), err)
}

/// Node name (empty for unnamed nodes) as an owned string.
#[no_mangle]
pub extern "C" fn ts_tree_node_name(
    tree: *const TsTree,
    node: usize,
    out: *mut *mut c_char,
    err: *mut *mut c_char,
) -> i32 {
    let run = || {
        let t = handle(tree, "tree")?;
        t.check_node(node)?;
        let name = t.tree.name.get(node).map(String::as_str).unwrap_or("");
        write_string(out, name, "out")
    };
    finish(run(), err)
}

/// The tree as a Newick string (owned; release with `ts_string_free`).
#[no_mangle]
pub extern "C" fn ts_tree_write_newick(
    tree: *const TsTree,
    out: *mut *mut c_char,
    err: *mut *mut c_char,
) -> i32 {
    let run = || {
        let t = handle(tree, "tree")?;
        write_string(out, &newick::write(&t.tree), "out")
    };
    finish(run(), err)
}

/// Name of the `k`-th tip in tip order as an owned string.
#[no_mangle]
pub extern "C" fn ts_tree_tip_name(
    tree: *const TsTree,
    k: usize,
    out: *mut *mut c_char,
    err: *mut *mut c_char,
) -> i32 {
    let run = || {
        let t = handle(tree, "tree")?;
        let name = t
            .tips
            .get(k)
            .ok_or_else(|| Failure::invalid(format!("tip index {k} out of range")))?;
        write_string(out, name, "out")
    };
    finish(run(), err)
}
