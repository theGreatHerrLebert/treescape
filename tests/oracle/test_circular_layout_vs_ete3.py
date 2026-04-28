"""Oracle runner for claim ``treescape-circular-layout-vs-ete3``.

ete3 does not expose its circular-mode layout coordinates outside the
Qt renderer — same situation as the rectangular ete3 test. We follow
the same indirect strategy:

* ``r`` per tip ↔ ``ete3.Tree.get_distance(leaf)`` (cumulative branch
  length; identical convention to rectangular x).
* ``θ`` per tip is derived from the tip's pre-order index in ete3's
  ``iter_leaves()`` traversal, applied to the treescape convention
  formula (``start_angle - i/N · sweep_total``). If ete3 and treescape
  agree on tip pre-order, the θ values will match exactly.

The substantive check: ete3's traversal and distance computation
produce the same `(r, θ)` we do. ete3 does NOT independently verify
treescape's wrap-aware internal-node mean (impossible without ete3
exposing internal-node circular coords) — that piece is covered by
the Rust↔reference parity claim.

Tolerance ``1e-6`` to absorb ete3 internal float ordering.
"""

from __future__ import annotations

import json
import math
import pathlib
import time

import pytest

from treescape_reference.layout import circular_layout, tips_by_name
from treescape_reference.newick import parse as ref_parse

try:
    from ete3 import Tree as Ete3Tree

    HAVE_ETE3 = True
except ImportError:  # pragma: no cover
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
START_ANGLE = math.pi / 2.0
SWEEP_TOTAL = 2.0 * math.pi


def _ete3_tip_polar(src: str) -> dict[str, tuple[float, float]]:
    t = Ete3Tree(src, format=1)
    leaves = list(t.iter_leaves())
    n = len(leaves)
    out: dict[str, tuple[float, float]] = {}
    for i, leaf in enumerate(leaves):
        r = float(t.get_distance(leaf))
        theta = START_ANGLE - (i / n) * SWEEP_TOTAL if n > 1 else START_ANGLE
        out[leaf.name] = (r, theta)
    return out


@pytest.mark.skipif(not HAVE_ETE3, reason="ete3 not installed")
@pytest.mark.parametrize("fixture", LAYOUT_SAFE_FIXTURES, ids=lambda p: p.name)
def test_circular_layout_vs_ete3(fixture: pathlib.Path) -> None:
    src = fixture.read_text()
    tree = ref_parse(src)
    coords = circular_layout(tree)
    ours = tips_by_name(tree, coords)
    theirs = _ete3_tip_polar(src)
    assert set(ours) == set(theirs), (
        f"tip name set differs on {fixture.name}: ours={set(ours)} ete3={set(theirs)}"
    )
    for name in ours:
        orad, oth = ours[name]
        erad, eth = theirs[name]
        assert abs(orad - erad) < TOL, (
            f"r mismatch on {fixture.name}/{name}: ours={orad} ete3={erad}"
        )
        assert abs(oth - eth) < TOL, (
            f"θ mismatch on {fixture.name}/{name}: ours={oth} ete3={eth}"
        )


@pytest.fixture(scope="session", autouse=True)
def _emit_report() -> None:
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-circular-layout-vs-ete3",
        "version": "0.1",
        "timestamp_utc": int(time.time()),
        "fixtures": [f.name for f in LAYOUT_SAFE_FIXTURES],
        "tolerance": TOL,
        "ete3_available": HAVE_ETE3,
        "tier": "ci",
    }
    (REPORT_DIR / "circular_layout_vs_ete3.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
