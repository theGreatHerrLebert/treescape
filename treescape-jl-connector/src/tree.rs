//! Tree handle: parse, inspect, free.

use std::ffi::c_char;

use treescape_core::ladderize::tip_order;
use treescape_core::newick;
use treescape_core::tree::Tree;

use crate::ffi::{copy_out, finish, handle, str_arg, write_out, write_string, Failure, FfiResult};
use crate::TS_PARSE_ERROR;

/// Largest Newick input accepted (64 MiB; a million-tip tree is ~30 MB).
/// Parsing amplifies input size several-fold, and allocation failure
/// aborts the host process, so oversized input is rejected up front.
/// This bounds the common case; it cannot rule out allocation failure
/// under arbitrary memory pressure.
pub const MAX_NEWICK_BYTES: usize = 64 * 1024 * 1024;

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
