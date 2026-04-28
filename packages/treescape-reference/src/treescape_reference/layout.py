"""Readable rectangular phylogram layout.

This module is the **canonical convention owner** for treescape. The
Rust port in ``treescape-core`` must agree with these conventions
within 1e-9 (claim ``treescape-layout-rust-vs-reference``). The
external oracles (ete3, Biopython, ggtree) are checked against the
output of *this* module — disagreements surface as documented
convention gaps in ``docs/conventions.md`` rather than as silent
tolerance bumps.

Conventions (v0.1, rectangular layout only):

* **x = cumulative branch length from root.** Root has ``x = 0``.
  Each child has ``x = parent.x + child.branch_length``. Negative
  branch lengths produce negative offsets (legal but rare).

* **y for tips = 0, 1, 2, ..., N - 1 in pre-order traversal of leaves.**
  Topmost tip in pre-order has ``y = 0``. This is the ete3 default.
  Note: Biopython uses 1-indexed tip y; the Biopython oracle test
  subtracts 1 for parity.

* **y for internal nodes = arithmetic mean of immediate children's y.**
  For binary trees this matches Biopython's "midpoint of first and
  last child" exactly. For multifurcating internal nodes the two
  conventions can differ; for the trifurcation_root.nwk fixture they
  happen to coincide. The first multifurcation case where they diverge
  will be added under v0.2.

* **Layout key by Python id:** the layout returns
  ``dict[id(Node), (x, y)]``. The ``tips_by_name`` helper extracts the
  tip subset keyed by name for cross-oracle comparison.
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

from .newick import Node, Tree


Coords = Tuple[float, float]


def rectangular_layout(tree: Tree) -> Dict[int, Coords]:
    """Compute (x, y) for every node in a rectangular phylogram.

    The returned dict is keyed by ``id(node)``; pair with
    :func:`tips_by_name` if you only need tip coordinates.

    Pure function: does not mutate ``tree``.
    """
    if tree.root is None:
        return {}

    preorder = _preorder(tree.root)

    x: Dict[int, float] = {id(tree.root): 0.0}
    for node in preorder:
        for child in node.children:
            x[id(child)] = x[id(node)] + child.branch_length

    y: Dict[int, float] = {}
    tip_index = 0
    for node in preorder:
        if node.is_tip():
            y[id(node)] = float(tip_index)
            tip_index += 1

    for node in _postorder(tree.root):
        if node.is_tip():
            continue
        if not node.children:
            y[id(node)] = 0.0
            continue
        child_y = [y[id(c)] for c in node.children]
        y[id(node)] = sum(child_y) / len(child_y)

    return {key: (x[key], y[key]) for key in x}


def find_mrca(tree: Tree, tip_names: List[str]) -> Node:
    """Most-recent-common-ancestor of the given tip names.

    Raises ``KeyError`` if any name isn't found, ``ValueError`` if
    ``tip_names`` is empty. With a single tip name, returns that tip
    (its own MRCA).
    """
    if not tip_names:
        raise ValueError("find_mrca requires at least one tip name")
    if tree.root is None:
        raise ValueError("find_mrca on an empty tree")

    requested = list(tip_names)
    node_for: Dict[str, Node] = {}
    for n in _postorder(tree.root):
        if n.is_tip() and n.name in requested and n.name not in node_for:
            node_for[n.name] = n
    missing = [t for t in requested if t not in node_for]
    if missing:
        raise KeyError(f"tip(s) not found: {missing}")

    parent_of: Dict[int, Node] = {}
    for n in _postorder(tree.root):
        for c in n.children:
            parent_of[id(c)] = n

    def ancestors(n: Node) -> List[Node]:
        out = [n]
        while id(out[-1]) in parent_of:
            out.append(parent_of[id(out[-1])])
        return out

    if len(requested) == 1:
        return node_for[requested[0]]

    iter_names = iter(requested)
    common = set(id(a) for a in ancestors(node_for[next(iter_names)]))
    for name in iter_names:
        common &= set(id(a) for a in ancestors(node_for[name]))
    # Pick the deepest common ancestor: traverse from the first tip
    # upward and return the first ancestor in `common`.
    for a in ancestors(node_for[requested[0]]):
        if id(a) in common:
            return a
    raise AssertionError("no common ancestor — should be unreachable for a connected tree")


def clade_tips(tree: Tree, mrca: Node) -> List[Node]:
    """All tips in the subtree rooted at ``mrca``, in pre-order."""
    if mrca.is_tip():
        return [mrca]
    out: List[Node] = []
    for n in _preorder(mrca):
        if n.is_tip():
            out.append(n)
    return out


def tips_by_name(tree: Tree, coords: Dict[int, Coords]) -> Dict[str, Coords]:
    """Project ``coords`` to ``{tip_name: (x, y)}``. Skips empty names."""
    out: Dict[str, Coords] = {}
    if tree.root is None:
        return out
    for node in _postorder(tree.root):
        if not node.is_tip() or not node.name:
            continue
        out[node.name] = coords[id(node)]
    return out


def _preorder(root: Node) -> List[Node]:
    out: List[Node] = []
    stack: List[Node] = [root]
    while stack:
        n = stack.pop()
        out.append(n)
        for c in reversed(n.children):
            stack.append(c)
    return out


def _postorder(root: Node) -> List[Node]:
    out: List[Node] = []
    stack: List[Node] = [root]
    while stack:
        n = stack.pop()
        out.append(n)
        stack.extend(n.children)
    out.reverse()
    return out


def circular_layout(
    tree: Tree,
    *,
    start_angle: float = math.pi / 2,
    sweep_total: float = 2 * math.pi,
) -> Dict[int, Coords]:
    """Compute (r, θ) for every node in a circular phylogram.

    Per ``docs/conventions.md``: r is cumulative branch length from
    root (matching rectangular's x). θ for tips is
    ``start_angle - (i / N) * sweep_total`` for tip ``i`` in pre-order
    leaf traversal — clockwise from ``start_angle`` so the natural
    "reading" direction holds. θ for internal nodes is the wrap-aware
    arithmetic mean of children's angles, computed in vector space to
    avoid the 0-vs-2π discontinuity.

    Defaults: ``start_angle = π/2`` (12 o'clock), ``sweep_total = 2π``
    (full circle, default for circular phylograms; pass smaller values
    for fan layouts).

    Pure function: does not mutate ``tree``.
    """
    if tree.root is None:
        return {}

    preorder = _preorder(tree.root)

    r: Dict[int, float] = {id(tree.root): 0.0}
    for node in preorder:
        for child in node.children:
            r[id(child)] = r[id(node)] + child.branch_length

    tips = [n for n in preorder if n.is_tip()]
    n_tips = len(tips)
    theta: Dict[int, float] = {}
    if n_tips == 0:
        theta[id(tree.root)] = start_angle
        return {key: (r[key], theta[key]) for key in r}
    if n_tips == 1:
        # Degenerate circle: one tip, place at start_angle.
        theta[id(tips[0])] = start_angle
    else:
        for i, tip in enumerate(tips):
            theta[id(tip)] = start_angle - (i / n_tips) * sweep_total

    for node in _postorder(tree.root):
        if node.is_tip():
            continue
        if not node.children:
            theta[id(node)] = start_angle
            continue
        # Wrap-aware mean: convert each child θ to its unit vector,
        # average, then atan2. Equivalent to arithmetic mean when
        # children's angles span less than π.
        sx = sum(math.cos(theta[id(c)]) for c in node.children)
        sy = sum(math.sin(theta[id(c)]) for c in node.children)
        theta[id(node)] = math.atan2(sy, sx)

    return {key: (r[key], theta[key]) for key in r}


__all__ = [
    "Coords",
    "circular_layout",
    "clade_tips",
    "find_mrca",
    "rectangular_layout",
    "tips_by_name",
]
