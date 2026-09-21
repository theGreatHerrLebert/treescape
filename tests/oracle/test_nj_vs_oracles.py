"""Oracle runner for claim ``treescape-nj-vs-oracles``.

Neighbor joining from both treescape implementations against
scikit-bio's ``nj`` (``neg_as_zero=False``: keep negative lengths, as
treescape does) and Biopython's ``DistanceTreeConstructor.nj``, compared
as unrooted trees (``_distances.splits``): identical split sets, edge
lengths within 1e-9. Every matrix is first proven tie-free
(``assert_tie_free``); a tied matrix fails instead of being skipped.
"""

from __future__ import annotations

import functools
import json
import time

import pytest

from _distances import DISTANCE_CASES, assert_same_splits, assert_tie_free, build, from_clades, splits
from _julia import REPO

skbio = pytest.importorskip("skbio", reason="scikit-bio not installed")
from Bio.Phylo.TreeConstruction import DistanceMatrix as BioDM  # noqa: E402
from Bio.Phylo.TreeConstruction import DistanceTreeConstructor  # noqa: E402

REPORT_DIR = REPO / "tests" / "oracle" / "reports"
TOL = 1e-9
ORACLES = ("scikit-bio", "Biopython")
CASES = [(c, impl, o) for c in DISTANCE_CASES for impl in ("reference", "rust") for o in ORACLES]


@functools.cache
def oracle_splits(case, oracle: str) -> dict:
    labels = list(case.labels)
    if oracle == "scikit-bio":
        dm = skbio.DistanceMatrix([list(r) for r in case.matrix], labels)
        tree = skbio.tree.nj(dm, neg_as_zero=False)
        topo = from_clades(tree, lambda n: n.children, lambda n: n.length, lambda n: n.name)
    else:
        lower = [[case.matrix[i][j] for j in range(i + 1)] for i in range(len(labels))]
        tree = DistanceTreeConstructor().nj(BioDM(labels, lower))
        topo = from_clades(tree.root, lambda c: c.clades, lambda c: c.branch_length, lambda c: c.name)
    return splits(topo, labels[0])


@pytest.mark.parametrize("case,impl,oracle", CASES, ids=[f"{c.id}-{i}-{o}" for c, i, o in CASES])
def test_nj_vs_oracle(case, impl, oracle) -> None:
    assert_tie_free(case, "nj")
    ours = splits(build(case, "nj", impl), case.labels[0])
    assert_same_splits(ours, oracle_splits(case, oracle), TOL, f"{case.id} ({impl} vs {oracle})")


@pytest.fixture(scope="session", autouse=True)
def _emit_report():
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    import Bio

    summary = {
        "claim": "treescape-nj-vs-oracles",
        "version": "0.6",
        "timestamp_utc": int(time.time()),
        "cases": [c.id for c in DISTANCE_CASES],
        "implementations": ["reference", "rust"],
        "oracles": {"scikit-bio": skbio.__version__, "Biopython": Bio.__version__},
        "tolerance": TOL,
    }
    (REPORT_DIR / "nj_vs_oracles.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
