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


__all__ = ["Coords", "rectangular_layout", "tips_by_name"]
