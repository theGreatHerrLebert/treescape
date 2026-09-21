"""Oracle runner for claim ``treescape-upgma-vs-scipy``.

UPGMA from both treescape implementations against
``scipy.cluster.hierarchy.linkage(method="average")``, compared as rooted
trees (``_distances.heights``): identical clade sets, node heights
(half the merge distance) within 1e-9. Every matrix is first proven
tie-free. Biopython's ``upgma`` is WPGMA and scikit-bio's wraps SciPy, so
neither is used (``docs/conventions.md``).
"""

from __future__ import annotations

import functools
import json
import time

import pytest

from _distances import DISTANCE_CASES, assert_same_heights, assert_tie_free, build, heights
from _julia import REPO

scipy = pytest.importorskip("scipy", reason="SciPy not installed")
from scipy.cluster.hierarchy import linkage  # noqa: E402
from scipy.spatial.distance import squareform  # noqa: E402

REPORT_DIR = REPO / "tests" / "oracle" / "reports"
TOL = 1e-9
CASES = [(c, impl) for c in DISTANCE_CASES for impl in ("reference", "rust")]


@functools.cache
def scipy_heights(case) -> dict:
    import numpy as np

    n = len(case.labels)
    z = linkage(squareform(np.array(case.matrix), checks=False), method="average")
    clade = {i: frozenset([case.labels[i]]) for i in range(n)}
    out = {clade[i]: 0.0 for i in range(n)}
    for row, (a, b, dist, _) in enumerate(z):
        clade[n + row] = clade[int(a)] | clade[int(b)]
        out[clade[n + row]] = float(dist) / 2
    return out


@pytest.mark.parametrize("case,impl", CASES, ids=[f"{c.id}-{i}" for c, i in CASES])
def test_upgma_vs_scipy(case, impl) -> None:
    assert_tie_free(case, "upgma")
    ours = heights(build(case, "upgma", impl))
    assert_same_heights(ours, scipy_heights(case), TOL, f"{case.id} ({impl} vs SciPy)")


@pytest.fixture(scope="session", autouse=True)
def _emit_report():
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-upgma-vs-scipy",
        "version": "0.6",
        "timestamp_utc": int(time.time()),
        "cases": [c.id for c in DISTANCE_CASES],
        "implementations": ["reference", "rust"],
        "scipy_version": scipy.__version__,
        "tolerance": TOL,
    }
    (REPORT_DIR / "upgma_vs_scipy.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
