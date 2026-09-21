"""Oracle runner for claim ``treescape-circular-layout-vs-ggtree`` (release tier).

``workflow/scripts/oracle_ggtree.R --circular`` runs
``ggtree(tree, layout = "circular", ladderize = FALSE)`` and prints r and
θ (radians) for every node. Compared, for both treescape implementations
on the ``layout-v2`` corpus, nodes matched by clade:

* r of every node;
* θ of every tip, after the per-tip transform
  ``θ_ggtree = 2π/N + π/2 − θ_ours`` (mod 2π): ggtree sweeps
  counter-clockwise with the last tip at 3 o'clock, treescape clockwise
  from 12 o'clock (``docs/conventions.md``, disagreement log).

Internal θ is not compared: ggtree takes the linear mean of the child
angles, treescape the wrap-aware vector mean. Tolerance: 1e-3.
"""

from __future__ import annotations

import json
import math
import time

import pytest

import _ggtree
from _julia import REPO
from _release import require
from _layouts import CASE_IDS, CASES, LAYOUT_CORPUS, angle_diff, circular, label

REPORT_DIR = REPO / "tests" / "oracle" / "reports"
TOL = 1e-3


@pytest.mark.release_only
@pytest.mark.parametrize("fixture,impl", CASES, ids=CASE_IDS)
def test_circular_layout_vs_ggtree(fixture, impl) -> None:
    require(_ggtree.available(), "R + Bioconductor + ggtree")
    ours = circular(fixture.read_text(), impl)
    theirs = _ggtree.nodes(str(fixture), circular=True)
    assert set(ours) == set(theirs), f"clade sets differ on {fixture.name}"
    n_tips = sum(1 for clade in ours if len(clade) == 1)
    offset = 2.0 * math.pi / n_tips + math.pi / 2.0
    for clade, row in theirs.items():
        orad, oth = ours[clade]
        grad, gth = float(row["r"]), float(row["theta"])
        assert abs(orad - grad) < TOL, f"r mismatch on {fixture.name}/{label(clade)} ({impl}): ours={orad} ggtree={grad}"
        if row["is_tip"].upper() == "TRUE":
            d = angle_diff(offset - oth, gth)
            assert d < TOL, (
                f"θ mismatch on {fixture.name}/{label(clade)} ({impl}): "
                f"ours={oth} expected_ggtree={offset - oth} got={gth} delta={d}"
            )


@pytest.fixture(scope="session", autouse=True)
def _emit_report():
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-circular-layout-vs-ggtree",
        "version": "0.6",
        "timestamp_utc": int(time.time()),
        "corpus": "layout-v2",
        "fixtures": [f"{f.parent.name}/{f.name}" for f in LAYOUT_CORPUS],
        "implementations": ["reference", "rust"],
        "compared": "r of every node; θ of every tip (after the documented transform)",
        "tolerance": TOL,
        "ggtree_available": _ggtree.available(),
    }
    (REPORT_DIR / "circular_layout_vs_ggtree.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
