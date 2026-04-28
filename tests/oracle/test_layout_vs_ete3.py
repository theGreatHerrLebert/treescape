"""Oracle runner for claim ``treescape-layout-vs-ete3``.

ete3 does not expose layout coordinates as a clean public API — its
coords are produced inside the Qt-based renderer. We instead use ete3's
canonical tree primitives as the oracle:

* tip pre-order: ``ete3.Tree.iter_leaves()`` walks leaves in pre-order DFS.
* x for any tip: ``ete3.Tree.get_distance(target=leaf, topology_only=False)``
  from root to leaf is the cumulative branch length, matching our x.
* y for tips: index in ``iter_leaves()`` order.

Agreement here means ete3's tree traversal and distance computation
produce the same coordinates we do, given the same fixture. This is
indirect (we don't validate ete3's renderer) but the conventions tested
are exactly the ones a phylogram visualizer must agree on.

Tolerance: 1e-6 absolute, looser than the Rust↔reference 1e-9 to absorb
ete3's float arithmetic ordering differences.
"""

from __future__ import annotations

import json
import pathlib
import time

import pytest

from treescape_reference.layout import rectangular_layout, tips_by_name
from treescape_reference.newick import parse as ref_parse

try:
    from ete3 import Tree as Ete3Tree

    HAVE_ETE3 = True
except ImportError:  # pragma: no cover - environment-dependent
    HAVE_ETE3 = False


FIXTURES_DIR = pathlib.Path(__file__).parent.parent / "fixtures" / "trees"
REPORT_DIR = pathlib.Path(__file__).parent / "reports"

LAYOUT_SAFE_FIXTURES = [
    FIXTURES_DIR / "small" / "two_tip.nwk",
    FIXTURES_DIR / "small" / "balanced_4.nwk",
    FIXTURES_DIR / "small" / "unbalanced_5.nwk",
    FIXTURES_DIR / "edge" / "trifurcation_root.nwk",
]

TOL = 1e-6


def _ete3_tip_coords(src: str) -> dict[str, tuple[float, float]]:
    t = Ete3Tree(src, format=1)
    leaves = list(t.iter_leaves())
    out: dict[str, tuple[float, float]] = {}
    for i, leaf in enumerate(leaves):
        x = t.get_distance(leaf)
        out[leaf.name] = (float(x), float(i))
    return out


@pytest.mark.skipif(not HAVE_ETE3, reason="ete3 not installed")
@pytest.mark.parametrize("fixture", LAYOUT_SAFE_FIXTURES, ids=lambda p: p.name)
def test_layout_vs_ete3(fixture: pathlib.Path) -> None:
    src = fixture.read_text()
    tree = ref_parse(src)
    coords = rectangular_layout(tree)
    ours = tips_by_name(tree, coords)
    theirs = _ete3_tip_coords(src)
    assert set(ours) == set(theirs), (
        f"tip name set differs on {fixture.name}: ours={set(ours)} ete3={set(theirs)}"
    )
    for name in ours:
        ox, oy = ours[name]
        ex, ey = theirs[name]
        assert abs(ox - ex) < TOL, (
            f"x mismatch on {fixture.name}/{name}: ours={ox} ete3={ex}"
        )
        assert abs(oy - ey) < TOL, (
            f"y mismatch on {fixture.name}/{name}: ours={oy} ete3={ey}"
        )


@pytest.fixture(scope="session", autouse=True)
def _emit_report() -> None:
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-layout-vs-ete3",
        "version": "0.1",
        "timestamp_utc": int(time.time()),
        "fixtures": [f.name for f in LAYOUT_SAFE_FIXTURES],
        "tolerance": TOL,
        "ete3_available": HAVE_ETE3,
    }
    (REPORT_DIR / "layout_vs_ete3.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
