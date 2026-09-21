"""Oracle runner for claim ``treescape-layout-vs-ggtree`` (release tier).

``workflow/scripts/oracle_ggtree.R`` runs ``ggtree(tree, ladderize =
FALSE)`` and prints x/y for every node. Compared, for both treescape
implementations (Rust core, ``treescape-reference``) on the ``layout-v2``
corpus, nodes matched by clade: x and y of every node, with our y + 1 for
ggtree's 1-based tip rows (``docs/conventions.md``). Tolerance: 1e-4.
"""

from __future__ import annotations

import json
import time

import pytest

import _ggtree
from _julia import REPO
from _layouts import CASE_IDS, CASES, LAYOUT_CORPUS, label, rectangular

REPORT_DIR = REPO / "tests" / "oracle" / "reports"
TOL = 1e-4


@pytest.mark.release_only
@pytest.mark.skipif(not _ggtree.available(), reason="R + Bioconductor + ggtree required (release tier)")
@pytest.mark.parametrize("fixture,impl", CASES, ids=CASE_IDS)
def test_layout_vs_ggtree(fixture, impl) -> None:
    ours = rectangular(fixture.read_text(), impl)
    theirs = _ggtree.nodes(str(fixture))
    assert set(ours) == set(theirs), f"clade sets differ on {fixture.name}"
    for clade, row in theirs.items():
        ox, oy = ours[clade]
        gx, gy = float(row["x"]), float(row["y"])
        assert abs(ox - gx) < TOL, f"x mismatch on {fixture.name}/{label(clade)} ({impl}): ours={ox} ggtree={gx}"
        # ggtree y is 1-based; ours is 0-based. See docs/conventions.md.
        assert abs((oy + 1.0) - gy) < TOL, (
            f"y mismatch on {fixture.name}/{label(clade)} ({impl}): ours+1={oy + 1.0} ggtree={gy}"
        )


@pytest.fixture(scope="session", autouse=True)
def _emit_report():
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-layout-vs-ggtree",
        "version": "0.6",
        "timestamp_utc": int(time.time()),
        "corpus": "layout-v2",
        "fixtures": [f"{f.parent.name}/{f.name}" for f in LAYOUT_CORPUS],
        "implementations": ["reference", "rust"],
        "compared": "x and y of every node",
        "tolerance": TOL,
        "ggtree_available": _ggtree.available(),
    }
    (REPORT_DIR / "layout_vs_ggtree.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
