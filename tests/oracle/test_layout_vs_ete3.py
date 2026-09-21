"""Oracle runner for claim ``treescape-layout-vs-ete3``.

ete3 does not expose layout coordinates as a public API (they are made
inside its Qt renderer). Its tree primitives are the oracle instead:

* x of every node: ``Tree.get_distance(node)``, the cumulative branch
  length from the root, which is our x.
* y of every tip: the tip's index in ``Tree.iter_leaves()`` (pre-order).
  ete3 has no internal-y rule, so internal y is not compared.

Both treescape implementations (Rust core, ``treescape-reference``) are
compared on the ``layout-v2`` corpus, nodes matched by clade
(``_layouts.py``). Tolerance: 1e-6 absolute.
"""

from __future__ import annotations

import json
import time

import pytest

from _julia import REPO
from _layouts import CASE_IDS, CASES, LAYOUT_CORPUS, label, rectangular

ete3 = pytest.importorskip("ete3", reason="ete3 not installed")

REPORT_DIR = REPO / "tests" / "oracle" / "reports"
TOL = 1e-6


def ete3_nodes(src: str) -> dict[frozenset, tuple[float, float | None]]:
    """``{clade: (x, y or None)}``; y only for tips."""
    t = ete3.Tree(src, format=1)
    tip_y = {leaf.name: float(i) for i, leaf in enumerate(t.iter_leaves())}
    out = {}
    nodes = list(t.traverse("preorder"))
    for node in nodes:
        clade = frozenset(leaf.name for leaf in node.iter_leaves())
        out[clade] = (float(t.get_distance(node)), tip_y[node.name] if node.is_leaf() else None)
    assert len(out) == len(nodes), "ete3 clades do not identify nodes"
    return out


@pytest.mark.parametrize("fixture,impl", CASES, ids=CASE_IDS)
def test_layout_vs_ete3(fixture, impl) -> None:
    src = fixture.read_text()
    ours, theirs = rectangular(src, impl), ete3_nodes(src)
    assert set(ours) == set(theirs), f"clade sets differ on {fixture.name}"
    for clade, (ex, ey) in theirs.items():
        ox, oy = ours[clade]
        assert abs(ox - ex) < TOL, f"x mismatch on {fixture.name}/{label(clade)} ({impl}): ours={ox} ete3={ex}"
        if ey is not None:
            assert abs(oy - ey) < TOL, f"y mismatch on {fixture.name}/{label(clade)} ({impl}): ours={oy} ete3={ey}"


@pytest.fixture(scope="session", autouse=True)
def _emit_report():
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-layout-vs-ete3",
        "version": "0.6",
        "timestamp_utc": int(time.time()),
        "corpus": "layout-v2",
        "fixtures": [f"{f.parent.name}/{f.name}" for f in LAYOUT_CORPUS],
        "implementations": ["reference", "rust"],
        "compared": "x of every node; y of every tip",
        "tolerance": TOL,
        "ete3_version": ete3.__version__,
    }
    (REPORT_DIR / "layout_vs_ete3.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
