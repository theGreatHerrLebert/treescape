"""Oracle runner for claim ``treescape-tree-build-rust-vs-reference``.

The Rust tree builders (via ``treescape_connector``) against
``treescape_reference.tree_build`` on the ``distance-v1`` corpus and the
tie fixtures: identical topology including child order, identical tip
names, branch lengths within 1e-12. Ties are included on purpose — the
conventions pin the tie rule, so both must break every tie the same way.
"""

from __future__ import annotations

import json
import time

import pytest

from _distances import DISTANCE_CASES, TIE_CASES, Topo, build
from _julia import REPO

REPORT_DIR = REPO / "tests" / "oracle" / "reports"
TOL = 1e-12
CASES = [(c, m) for c in DISTANCE_CASES + TIE_CASES for m in ("nj", "upgma")]


def preorder(t: Topo) -> list:
    """``(name or None, number of children, length)`` in pre-order, children in order."""
    out, stack = [], [t.root]
    while stack:
        n = stack.pop()
        out.append((t.name.get(n), len(t.children[n]), t.length[n] if n != t.root else 0.0))
        stack.extend(reversed(t.children[n]))
    return out


@pytest.mark.parametrize("case,method", CASES, ids=[f"{c.id}-{m}" for c, m in CASES])
def test_rust_tree_matches_reference(case, method) -> None:
    rust, ref = preorder(build(case, method, "rust")), preorder(build(case, method, "reference"))
    assert [(n, k) for n, k, _ in rust] == [(n, k) for n, k, _ in ref], f"{case.id}/{method}: topology or order differs"
    for i, ((_, _, a), (_, _, b)) in enumerate(zip(rust, ref)):
        assert abs(a - b) < TOL, f"{case.id}/{method}: branch length at pre-order node {i}: rust={a} ref={b}"


@pytest.fixture(scope="session", autouse=True)
def _emit_report():
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-tree-build-rust-vs-reference",
        "version": "0.6",
        "timestamp_utc": int(time.time()),
        "cases": [c.id for c in DISTANCE_CASES + TIE_CASES],
        "methods": ["nj", "upgma"],
        "tolerance": TOL,
    }
    (REPORT_DIR / "tree_build_vs_reference.json").write_text(json.dumps(summary, indent=2, sort_keys=True))


@pytest.mark.parametrize("case", DISTANCE_CASES, ids=[c.id for c in DISTANCE_CASES])
def test_rust_from_linkage_matches_reference(case) -> None:
    """Both implementations read the same SciPy linkage matrix into the same tree."""
    pytest.importorskip("scipy")
    pytest.importorskip("treescape_connector.py_tree", reason="treescape_connector not built")
    import numpy as np
    from scipy.cluster.hierarchy import linkage
    from scipy.spatial.distance import squareform

    from _distances import from_reference, from_rust
    from treescape_connector.py_tree import Tree
    from treescape_reference import tree_build as ref

    z = linkage(squareform(np.array(case.matrix), checks=False), method="average")
    rust = preorder(from_rust(Tree.from_linkage([float(v) for row in z for v in row], list(case.labels))))
    ref_tree = preorder(from_reference(ref.from_linkage([list(map(float, row)) for row in z], list(case.labels))))
    assert [(n, k) for n, k, _ in rust] == [(n, k) for n, k, _ in ref_tree]
    for (_, _, a), (_, _, b) in zip(rust, ref_tree):
        assert abs(a - b) < TOL
