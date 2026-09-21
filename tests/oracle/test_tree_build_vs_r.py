"""Oracle runner for claims ``treescape-nj-vs-ape`` and
``treescape-upgma-vs-phangorn`` (release tier).

``workflow/scripts/oracle_tree_build.R`` builds every ``distance-v1``
matrix with ``ape::nj`` and ``phangorn::upgma`` in one R session per
method (matrices and trees cross as text with 17 significant digits).
NJ is compared unrooted (split sets, edge lengths), UPGMA rooted (clade
sets, node heights), both within 1e-9, against both treescape
implementations. Every matrix is first proven tie-free.
"""

from __future__ import annotations

import functools
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

from _distances import (
    DISTANCE_CASES,
    assert_same_heights,
    assert_same_splits,
    assert_tie_free,
    build,
    from_reference,
    heights,
    splits,
)
from _julia import REPO
from _release import require
from treescape_reference.newick import parse

REPORT_DIR = REPO / "tests" / "oracle" / "reports"
SCRIPT = REPO / "workflow" / "scripts" / "oracle_tree_build.R"
TOL = 1e-9
CASES = [(c, impl) for c in DISTANCE_CASES for impl in ("reference", "rust")]
IDS = [f"{c.id}-{i}" for c, i in CASES]


@functools.cache
def _have_r() -> bool:
    if shutil.which("Rscript") is None:
        return False
    probe = subprocess.run(
        ["Rscript", "-e", 'cat(requireNamespace("ape", quietly=TRUE) && requireNamespace("phangorn", quietly=TRUE))'],
        capture_output=True, text=True, check=False,
    )
    return probe.stdout.strip() == "TRUE"


@functools.cache
def r_trees(method: str) -> dict:
    """``{case id: Newick}`` from one R run over the whole corpus."""
    with tempfile.TemporaryDirectory() as tmp:
        for case in DISTANCE_CASES:
            rows = ["\t".join(case.labels)] + ["\t".join(f"{v:.17g}" for v in row) for row in case.matrix]
            (Path(tmp) / f"{case.id}.tsv").write_text("\n".join(rows) + "\n")
        out = subprocess.run(["Rscript", str(SCRIPT), method, tmp], capture_output=True, text=True, check=True).stdout
    return dict(line.split("\t", 1) for line in out.splitlines() if line)


@pytest.mark.release_only
@pytest.mark.parametrize("case,impl", CASES, ids=IDS)
def test_nj_vs_ape(case, impl) -> None:
    require(_have_r(), "R with ape and phangorn")
    assert_tie_free(case, "nj")
    theirs = splits(from_reference(parse(r_trees("nj")[case.id])), case.labels[0])
    ours = splits(build(case, "nj", impl), case.labels[0])
    assert_same_splits(ours, theirs, TOL, f"{case.id} ({impl} vs ape::nj)")


@pytest.mark.release_only
@pytest.mark.parametrize("case,impl", CASES, ids=IDS)
def test_upgma_vs_phangorn(case, impl) -> None:
    require(_have_r(), "R with ape and phangorn")
    assert_tie_free(case, "upgma")
    theirs = heights(from_reference(parse(r_trees("upgma")[case.id])))
    ours = heights(build(case, "upgma", impl))
    assert_same_heights(ours, theirs, TOL, f"{case.id} ({impl} vs phangorn::upgma)")


@pytest.fixture(scope="session", autouse=True)
def _emit_report():
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claims": ["treescape-nj-vs-ape", "treescape-upgma-vs-phangorn"],
        "version": "0.6",
        "timestamp_utc": int(time.time()),
        "cases": [c.id for c in DISTANCE_CASES],
        "implementations": ["reference", "rust"],
        "tolerance": TOL,
        "r_available": _have_r(),
    }
    (REPORT_DIR / "tree_build_vs_r.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
