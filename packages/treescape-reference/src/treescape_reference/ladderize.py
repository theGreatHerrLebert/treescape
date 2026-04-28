"""Readable ladderization.

Sorts children at every internal node by subtree size. Tie-break is
``preserve original child order``, which matches ete3's default
behavior on the canonical fixtures.

Documented as part of claim ``treescape-ladderize-order``.
"""

from __future__ import annotations

from typing import Dict, List

from .newick import Node, Tree


def ladderize(tree: Tree, ascending: bool = True) -> None:
    """Reorder children in place by subtree size.

    Tie-break (matches ete3 — see docs/conventions.md):

    * ``ascending=True`` (ete3 ``direction=0``): stable ascending sort.
      Ties preserve original child order.
    * ``ascending=False`` (ete3 ``direction=1``): sort key is
      ``(-size, -original_position)`` ascending — equivalent to
      reversing tied groups.
    """
    if tree.root is None:
        return

    sizes: Dict[int, int] = {}
    _compute_subtree_sizes(tree.root, sizes)

    for node in _postorder(tree.root):
        if not node.children:
            continue
        if ascending:
            node.children.sort(key=lambda c: sizes[id(c)])
        else:
            indexed = list(enumerate(node.children))
            indexed.sort(key=lambda pair: (-sizes[id(pair[1])], -pair[0]))
            node.children[:] = [c for _, c in indexed]


def tip_order(tree: Tree) -> List[str]:
    """Return tips in pre-order traversal as the visible top-to-bottom order."""
    if tree.root is None:
        return []
    out: List[str] = []
    stack: List[Node] = [tree.root]
    while stack:
        n = stack.pop()
        if n.is_tip():
            out.append(n.name)
        for c in reversed(n.children):
            stack.append(c)
    return out


def _compute_subtree_sizes(root: Node, sizes: Dict[int, int]) -> int:
    """Postorder fill of subtree sizes (leaves count as 1)."""
    for node in _postorder(root):
        if not node.children:
            sizes[id(node)] = 1
        else:
            sizes[id(node)] = sum(sizes[id(c)] for c in node.children)
    return sizes[id(root)]


def _postorder(root: Node) -> List[Node]:
    out: List[Node] = []
    stack: List[Node] = [root]
    while stack:
        n = stack.pop()
        out.append(n)
        stack.extend(n.children)
    out.reverse()
    return out


__all__ = ["ladderize", "tip_order"]
