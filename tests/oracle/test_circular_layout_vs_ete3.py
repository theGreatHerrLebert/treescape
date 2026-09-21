"""Oracle runner for claim ``treescape-circular-layout-vs-ete3``.

ete3 does not expose its circular-mode coordinates (they are made inside
its Qt renderer), so this checks what ete3's tree primitives can:

* r of every node: ``Tree.get_distance(node)``, identical to rectangular x.
* θ of every tip: treescape's documented angle formula
  (``start_angle - i/N · sweep_total``) applied to the tip's index in
  ``Tree.iter_leaves()``. This checks tip *order*, not the angle rule;
  the rule is checked against ggtree (release tier) and by Rust<->reference
  parity.

Both treescape implementations are compared on the ``layout-v2`` corpus,
nodes matched by clade (``_layouts.py``). Tolerance: 1e-6 absolute.
"""

from __future__ import annotations

import json
import math
import time

import pytest

from _julia import REPO
from _layouts import CASE_IDS, CASES, LAYOUT_CORPUS, angle_diff, circular, label

ete3 = pytest.importorskip("ete3", reason="ete3 not installed")

REPORT_DIR = REPO / "tests" / "oracle" / "reports"
TOL = 1e-6
START_ANGLE = math.pi / 2.0
SWEEP_TOTAL = 2.0 * math.pi


def ete3_polar(src: str) -> dict[frozenset, tuple[float, float | None]]:
    """``{clade: (r, θ or None)}``; θ only for tips."""
    t = ete3.Tree(src, format=1)
    leaves = list(t.iter_leaves())
    n = len(leaves)
    tip_theta = {
        leaf.name: START_ANGLE - (i / n) * SWEEP_TOTAL if n > 1 else START_ANGLE
        for i, leaf in enumerate(leaves)
    }
    out = {}
    nodes = list(t.traverse("preorder"))
    for node in nodes:
        clade = frozenset(leaf.name for leaf in node.iter_leaves())
        out[clade] = (float(t.get_distance(node)), tip_theta[node.name] if node.is_leaf() else None)
    assert len(out) == len(nodes), "ete3 clades do not identify nodes"
    return out


@pytest.mark.parametrize("fixture,impl", CASES, ids=CASE_IDS)
def test_circular_layout_vs_ete3(fixture, impl) -> None:
    src = fixture.read_text()
    ours, theirs = circular(src, impl), ete3_polar(src)
    assert set(ours) == set(theirs), f"clade sets differ on {fixture.name}"
    for clade, (er, et) in theirs.items():
        orad, oth = ours[clade]
        assert abs(orad - er) < TOL, f"r mismatch on {fixture.name}/{label(clade)} ({impl}): ours={orad} ete3={er}"
        if et is not None:
            d = angle_diff(oth, et)
            assert d < TOL, f"θ mismatch on {fixture.name}/{label(clade)} ({impl}): ours={oth} ete3={et} delta={d}"


@pytest.fixture(scope="session", autouse=True)
def _emit_report():
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-circular-layout-vs-ete3",
        "version": "0.6",
        "timestamp_utc": int(time.time()),
        "corpus": "layout-v2",
        "fixtures": [f"{f.parent.name}/{f.name}" for f in LAYOUT_CORPUS],
        "implementations": ["reference", "rust"],
        "compared": "r of every node; θ of every tip (from ete3 leaf order)",
        "tolerance_asserted": TOL,
        "ete3_version": ete3.__version__,
    }
    (REPORT_DIR / "circular_layout_vs_ete3.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
