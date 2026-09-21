"""Shared harness for the tree-building claims (v0.6 Phase 3).

* ``DISTANCE_CASES``: the generated ``distance-v1`` corpus
  (``scripts/gen_distance_matrices.py``); ``TIE_CASES``: the hand-written
  tie fixtures in ``tests/fixtures/distances/``.
* ``build(case, method, impl)``: a tree from ``treescape-reference`` or
  the Rust core, as a ``Topo`` (edges keyed by tip sets).
* ``splits`` / ``heights``: the unrooted and rooted comparison keys from
  ``docs/conventions.md`` ("Comparing trees"), for any of the tree
  representations the oracles return.
"""

from __future__ import annotations

import functools
import sys
from dataclasses import dataclass

import pytest

from _julia import REPO
from treescape_reference import tree_build as ref

sys.path.insert(0, str(REPO / "scripts"))
from gen_distance_matrices import Case, corpus  # noqa: E402

DISTANCE_CASES: list[Case] = corpus()
TIE_DIR = REPO / "tests" / "fixtures" / "distances"
TIE_TOL = 1e-9


def _read_tsv(path) -> Case:
    lines = path.read_text().splitlines()
    labels = tuple(lines[0].split("\t"))
    rows = tuple(tuple(float(v) for v in line.split("\t")) for line in lines[1:])
    return Case(path.stem, labels, rows, "", False)


TIE_CASES: list[Case] = [_read_tsv(p) for p in sorted(TIE_DIR.glob("*.tsv"))]


@dataclass
class Topo:
    """A tree as ``(parent_id, child_id, length)`` edges plus tip names."""

    root: object
    children: dict  # node id -> list of child ids, in order
    length: dict  # node id -> branch length above it
    name: dict  # node id -> tip name (tips only)


def from_reference(tree) -> Topo:
    children, length, name = {}, {}, {}
    stack = [tree.root]
    while stack:
        n = stack.pop()
        children[id(n)] = [id(c) for c in n.children]
        length[id(n)] = float(n.branch_length or 0.0)
        if n.is_tip():
            name[id(n)] = n.name
        stack.extend(n.children)
    return Topo(id(tree.root), children, length, name)


def from_rust(tree) -> Topo:
    ids = tree.postorder()
    return Topo(
        tree.root,
        {i: list(tree.children(i)) for i in ids},
        {i: float(tree.branch_len(i)) for i in ids},
        {i: tree.name(i) for i in ids if tree.is_tip(i)},
    )


def from_clades(root, kids, blen, label) -> Topo:
    """Any object tree (Biopython Clade, scikit-bio TreeNode)."""
    children, length, name = {}, {}, {}
    stack = [root]
    while stack:
        n = stack.pop()
        cs = list(kids(n))
        children[id(n)] = [id(c) for c in cs]
        length[id(n)] = float(blen(n) or 0.0)
        if not cs:
            name[id(n)] = label(n)
        stack.extend(cs)
    return Topo(id(root), children, length, name)


def build(case: Case, method: str, impl: str) -> Topo:
    if impl == "reference":
        fn = ref.neighbor_joining if method == "nj" else ref.upgma
        return from_reference(fn([list(r) for r in case.matrix], list(case.labels)))
    pytest.importorskip("treescape_connector.py_tree", reason="treescape_connector not built")
    from treescape_connector.py_tree import Tree

    flat = [v for row in case.matrix for v in row]
    return from_rust(Tree.from_distances(flat, list(case.labels), method))


def _tipsets(t: Topo) -> dict:
    below = {}
    order, stack = [], [t.root]
    while stack:
        n = stack.pop()
        order.append(n)
        stack.extend(t.children[n])
    for n in reversed(order):
        kids = t.children[n]
        below[n] = frozenset([t.name[n]]) if not kids else frozenset().union(*(below[k] for k in kids))
    return below


def splits(t: Topo, first_label: str) -> dict:
    """Unrooted edges: ``{split: length}``, a split being the side of the
    edge that does not contain ``first_label``. A two-child root's two
    edges are the same split, so their lengths add."""
    below = _tipsets(t)
    everything = below[t.root]
    out: dict = {}
    for n, tips in below.items():
        if n == t.root:
            continue
        key = everything - tips if first_label in tips else tips
        out[key] = out.get(key, 0.0) + t.length[n]
    return out


def heights(t: Topo) -> dict:
    """Rooted clades: ``{clade: height}``, height = path length from the
    node down to its first tip (UPGMA trees are ultrametric)."""
    below = _tipsets(t)
    out = {}
    for n, tips in below.items():
        h, m = 0.0, n
        while t.children[m]:
            m = t.children[m][0]
            h += t.length[m]
        out[tips] = h
    return out


def assert_same_splits(ours: dict, theirs: dict, tol: float, what: str) -> None:
    assert set(ours) == set(theirs), (
        f"{what}: split sets differ; only ours {len(set(ours) - set(theirs))}, only theirs {len(set(theirs) - set(ours))}"
    )
    for key, length in ours.items():
        assert abs(length - theirs[key]) < tol, f"{what}: edge above {sorted(key)[:3]}.. ours={length} theirs={theirs[key]}"


def assert_same_heights(ours: dict, theirs: dict, tol: float, what: str) -> None:
    assert set(ours) == set(theirs), f"{what}: clade sets differ"
    for key, h in ours.items():
        assert abs(h - theirs[key]) < tol, f"{what}: height of {sorted(key)[:3]}.. ours={h} theirs={theirs[key]}"


def assert_tie_free(case: Case, method: str) -> None:
    ties = _ties(case, method)
    assert not ties, f"{case.id}: {method} has tied joins (clusters, tied pairs) {ties[:3]}; oracles may break them differently"


@functools.cache
def _ties(case: Case, method: str) -> tuple:
    """Joins where several candidates are within TIE_TOL of the best
    (cached per matrix: every implementation/oracle pairing asks).

    Fail if any join had several candidates within TIE_TOL of the best,
    unless the tie cannot change the tree: NJ at four clusters, where a
    pair and its complementary pair always tie and give the same unrooted
    tree."""
    ties = []

    def hook(r, candidates):
        best = min(v for v, _, _ in candidates)
        tied = [(p, q) for v, p, q in candidates if abs(v - best) <= TIE_TOL * max(1.0, abs(best))]
        if len(tied) == 1:
            return
        if method == "nj" and r == 4 and len(tied) == 2:
            (p1, q1), (p2, q2) = tied
            if not ((p1 | q1) & (p2 | q2)):  # complementary pairs
                return
        ties.append((r, len(tied)))

    fn = ref.neighbor_joining if method == "nj" else ref.upgma
    fn([list(r) for r in case.matrix], list(case.labels), on_step=hook)
    return tuple(ties)
