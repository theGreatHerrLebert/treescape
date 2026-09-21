"""Runner for claim ``treescape-tree-build-performance`` (``-m bench``).

Runs ``scripts/bench_tree_build.py`` (median of 5 runs, single thread,
every contender's tree checked against treescape's first) and asserts the
claim's bounds on the measured ratios. Timing claims need a quiet machine,
so this runs only with ``-m bench`` (CI job ``bench``), never in the
ordinary ci tier.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from _julia import REPO

REPORT_DIR = REPO / "tests" / "oracle" / "reports"
SIZES = "500,1000,2000"
NJ_VS_SKBIO_MAX = 5.0
UPGMA_VS_SCIPY_MAX = 5.0


@pytest.fixture(scope="module")
def report() -> dict:
    subprocess.run(
        [sys.executable, str(REPO / "scripts" / "bench_tree_build.py"), "--sizes", SIZES, "--out", str(REPORT_DIR)],
        check=True,
    )
    return json.loads((REPORT_DIR / "tree_build_performance.json").read_text())


@pytest.mark.bench
def test_every_contender_built_the_same_tree(report) -> None:
    for row in report["rows"]:
        for key in ("skbio_nj", "scipy_average", "biopython_nj"):
            assert row[key] != "mismatch", f"n={row['n']}: {key} built a different tree"


@pytest.mark.bench
def test_nj_within_bound_of_scikit_bio(report) -> None:
    for row in report["rows"]:
        ratio = row["treescape_nj"] / row["skbio_nj"]
        assert ratio <= NJ_VS_SKBIO_MAX, f"n={row['n']}: treescape NJ is {ratio:.2f}x scikit-bio (bound {NJ_VS_SKBIO_MAX}x)"


@pytest.mark.bench
def test_nj_faster_than_biopython(report) -> None:
    timed = [r for r in report["rows"] if isinstance(r["biopython_nj"], float)]
    assert timed, "Biopython was not timed at any size"
    for row in timed:
        assert row["treescape_nj"] < row["biopython_nj"], f"n={row['n']}: treescape NJ not faster than Biopython"


@pytest.mark.bench
def test_upgma_within_bound_of_scipy(report) -> None:
    for row in report["rows"]:
        ratio = row["treescape_upgma"] / row["scipy_average"]
        assert ratio <= UPGMA_VS_SCIPY_MAX, f"n={row['n']}: treescape UPGMA is {ratio:.2f}x SciPy (bound {UPGMA_VS_SCIPY_MAX}x)"
