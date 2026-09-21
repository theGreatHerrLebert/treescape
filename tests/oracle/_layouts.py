"""Shared harness for the layout oracle claims (v0.6 Phase 2).

Every layout runner compares **both** treescape implementations (the
Rust core through ``treescape_connector`` and ``treescape-reference``)
with its oracle, on the ``layout-v2`` corpus from
``tests/fixtures/corpora.toml``. Nodes are matched by clade: the set of
tip names below them (a tip's clade is its own name). Conventions:
``docs/conventions.md``, "Layout oracle corpus and node-level comparison".
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

from _julia import REPO
from treescape_reference.layout import circular_layout as ref_circular
from treescape_reference.layout import rectangular_layout as ref_rectangular
from treescape_reference.newick import parse as ref_parse

sys.path.insert(0, str(REPO / "scripts"))
from corpus_sha import corpora  # noqa: E402

Clade = frozenset
Coords = dict[frozenset, tuple[float, float]]

LAYOUT_CORPUS: list[Path] = [REPO / p for p in corpora()["layout-v2"]]
IMPLEMENTATIONS = ("reference", "rust")
CASES = [(f, impl) for f in LAYOUT_CORPUS for impl in IMPLEMENTATIONS]
CASE_IDS = [f"{f.parent.name}/{f.name}-{impl}" for f, impl in CASES]


def _rust():
    pytest.importorskip("treescape_connector.py_layout", reason="treescape_connector not built")
    from treescape_connector import py_layout
    from treescape_connector.py_tree import Tree

    return Tree, py_layout


def _distinct(below: dict, what: str) -> dict:
    """Clades must identify nodes one to one: with duplicate tip names or a
    unary node two nodes share a clade, and the ``{clade: …}`` maps built
    from them would silently compare fewer nodes than the tree has."""
    assert len(set(below.values())) == len(below), f"{what}: clades do not identify nodes (duplicate names or unary node)"
    return below


def _reference_clades(tree) -> dict[int, frozenset]:
    below: dict[int, frozenset] = {}
    for n in tree.postorder():
        below[id(n)] = frozenset([n.name]) if n.is_tip() else frozenset().union(*(below[id(c)] for c in n.children))
    return _distinct(below, "reference tree")


def _rust_clades(tree) -> dict[int, frozenset]:
    below: dict[int, frozenset] = {}
    for i in tree.postorder():
        below[i] = frozenset([tree.name(i)]) if tree.is_tip(i) else frozenset().union(*(below[c] for c in tree.children(i)))
    assert len(below) == tree.n_nodes, "Rust postorder does not visit every node"
    return _distinct(below, "Rust tree")


def rectangular(src: str, impl: str) -> Coords:
    """``{clade: (x, y)}`` for every node."""
    if impl == "reference":
        tree = ref_parse(src)
        coords = ref_rectangular(tree)
        return {clade: coords[key] for key, clade in _reference_clades(tree).items()}
    Tree, py_layout = _rust()
    tree = Tree.parse_newick(src)
    lay = py_layout.rectangular_layout(tree)
    xs, ys = lay.x, lay.y
    return {clade: (xs[i], ys[i]) for i, clade in _rust_clades(tree).items()}


def circular(src: str, impl: str) -> Coords:
    """``{clade: (r, θ)}`` for every node (default start angle and sweep)."""
    if impl == "reference":
        tree = ref_parse(src)
        coords = ref_circular(tree)
        return {clade: coords[key] for key, clade in _reference_clades(tree).items()}
    Tree, py_layout = _rust()
    tree = Tree.parse_newick(src)
    lay = py_layout.circular_layout(tree)
    rs, ts = lay.r, lay.theta
    return {clade: (rs[i], ts[i]) for i, clade in _rust_clades(tree).items()}


def binary_subtrees(src: str) -> set[frozenset]:
    """Clades of the nodes whose whole subtree has no node with more than
    two children (tips included), from the reference parse."""
    tree = ref_parse(src)
    clades = _reference_clades(tree)
    binary: dict[int, bool] = {}
    for n in tree.postorder():
        binary[id(n)] = len(n.children) <= 2 and all(binary[id(c)] for c in n.children)
    return {clades[id(n)] for n in tree.postorder() if binary[id(n)]}


def clades_from_parents(rows: list[dict], id_key: str = "node", parent_key: str = "parent") -> dict[str, frozenset]:
    """Clade of every row of a (node, parent, is_tip, label) table, keyed by node id."""
    children: dict[str, list[str]] = {}
    for row in rows:
        if row[parent_key] != row[id_key]:
            children.setdefault(row[parent_key], []).append(row[id_key])
    by_id = {row[id_key]: row for row in rows}
    out: dict[str, frozenset] = {}

    def clade(node: str) -> frozenset:
        stack, order = [node], []
        while stack:
            n = stack.pop()
            order.append(n)
            stack.extend(children.get(n, []))
        for n in reversed(order):
            if n not in out:
                kids = children.get(n, [])
                out[n] = frozenset([by_id[n]["label"]]) if not kids else frozenset().union(*(out[k] for k in kids))
        return out[node]

    for row in rows:
        clade(row[id_key])
    assert len(out) == len(rows), "oracle table has duplicate node ids"
    return _distinct(out, "oracle table")


def angle_diff(a: float, b: float) -> float:
    """Smallest absolute difference of two angles, in radians."""
    d = (a - b) % (2.0 * math.pi)
    return abs(2.0 * math.pi - d if d > math.pi else d)


def label(clade: frozenset) -> str:
    """Short, stable description of a clade for failure messages."""
    names = sorted(clade)
    return names[0] if len(names) == 1 else f"({names[0]}..{names[-1]}, {len(names)} tips)"
