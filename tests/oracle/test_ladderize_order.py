"""Oracle runner for claim ``treescape-ladderize-order``.

Compares treescape's ladderized tip order against ete3's
``Tree.ladderize()``. The documented tie-break (stable sort, preserve
original child order) makes the result deterministic on every fixture
in our canonical set.
"""

from __future__ import annotations

import json
import pathlib
import time

import pytest

from treescape_reference.ladderize import ladderize as ref_ladderize, tip_order
from treescape_reference.newick import parse as ref_parse

try:
    from ete3 import Tree as Ete3Tree

    HAVE_ETE3 = True
except ImportError:  # pragma: no cover
    HAVE_ETE3 = False


FIXTURES_DIR = pathlib.Path(__file__).parent.parent / "fixtures" / "trees"
REPORT_DIR = pathlib.Path(__file__).parent / "reports"

LADDERIZE_FIXTURES = [
    FIXTURES_DIR / "small" / "two_tip.nwk",
    FIXTURES_DIR / "small" / "balanced_4.nwk",
    FIXTURES_DIR / "small" / "unbalanced_5.nwk",
    FIXTURES_DIR / "edge" / "trifurcation_root.nwk",
]


def _ete3_ladderized_tip_order(src: str, ascending: bool) -> list[str]:
    t = Ete3Tree(src, format=1)
    # ete3 ladderize: direction=0 ascending (small subtrees first),
    # direction=1 descending. There's no `ascending=` kwarg on older ete3.
    t.ladderize(direction=0 if ascending else 1)
    return [leaf.name for leaf in t.iter_leaves()]


@pytest.mark.skipif(not HAVE_ETE3, reason="ete3 not installed")
@pytest.mark.parametrize("fixture", LADDERIZE_FIXTURES, ids=lambda p: p.name)
@pytest.mark.parametrize("ascending", [True, False], ids=["asc", "desc"])
def test_ladderize_matches_ete3(fixture: pathlib.Path, ascending: bool) -> None:
    src = fixture.read_text()
    tree = ref_parse(src)
    ref_ladderize(tree, ascending=ascending)
    ours = tip_order(tree)
    theirs = _ete3_ladderized_tip_order(src, ascending=ascending)
    assert ours == theirs, (
        f"ladderize order mismatch on {fixture.name} ({'asc' if ascending else 'desc'}): "
        f"ours={ours} ete3={theirs}"
    )


@pytest.fixture(scope="session", autouse=True)
def _emit_report() -> None:
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-ladderize-order",
        "version": "0.1",
        "timestamp_utc": int(time.time()),
        "fixtures": [f.name for f in LADDERIZE_FIXTURES],
        "tie_break_rule": "stable sort, preserve original child order",
        "ete3_available": HAVE_ETE3,
    }
    (REPORT_DIR / "ladderize_order.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
