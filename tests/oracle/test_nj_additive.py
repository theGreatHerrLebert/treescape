"""Oracle runner for claim ``treescape-nj-recovers-additive-trees``.

For each additive matrix of ``distance-v1`` (path lengths of a binary
random tree with positive branch lengths), neighbor joining must return
the generating tree as an unrooted tree: identical split set, edge
lengths within 1e-9 of the generating tree's. Ground truth, not another
implementation.
"""

from __future__ import annotations

import json
import time

import pytest

from _distances import DISTANCE_CASES, assert_same_splits, build, from_reference, splits
from _julia import REPO
from treescape_reference.newick import parse

REPORT_DIR = REPO / "tests" / "oracle" / "reports"
TOL = 1e-9
ADDITIVE = [c for c in DISTANCE_CASES if c.additive]
CASES = [(c, impl) for c in ADDITIVE for impl in ("reference", "rust")]


@pytest.mark.parametrize("case,impl", CASES, ids=[f"{c.id}-{i}" for c, i in CASES])
def test_nj_recovers_generating_tree(case, impl) -> None:
    truth = splits(from_reference(parse(case.source)), case.labels[0])
    ours = splits(build(case, "nj", impl), case.labels[0])
    assert_same_splits(ours, truth, TOL, f"{case.id} ({impl} vs generating tree)")


@pytest.fixture(scope="session", autouse=True)
def _emit_report():
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-nj-recovers-additive-trees",
        "version": "0.6",
        "timestamp_utc": int(time.time()),
        "cases": [c.id for c in ADDITIVE],
        "implementations": ["reference", "rust"],
        "tolerance": TOL,
    }
    (REPORT_DIR / "nj_additive.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
