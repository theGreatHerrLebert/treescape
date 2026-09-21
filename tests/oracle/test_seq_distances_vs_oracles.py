"""Oracle runner for claim ``treescape-seq-distances-vs-scikit-bio``.

Every pair of every nucleotide alignment, every model (p, jc69, k2p):
both treescape implementations against scikit-bio's ``pdist``, ``jc69``
and ``k2p`` within 1e-12, pair by pair. Where scikit-bio returns NaN
(saturation, or no comparable column), treescape must raise for that pair.

At the exact K2P boundary (``L - 2s - v == 0`` or ``L - 2v == 0`` on the
integer counts) scikit-bio computes ``1 - 2P - Q`` in floating point, gets
about 5.5e-17 and returns a finite distance near 19; treescape decides
saturation on the counts and raises (``docs/conventions.md``, disagreement
log). Those pairs are excluded by that rule and listed in the report.
"""

from __future__ import annotations

import json
import math
import time

import pytest

from _alignments import ALIGNMENTS, exact_boundary
from _julia import REPO
from treescape_reference import seq_distance as ref

skbio = pytest.importorskip("skbio", reason="scikit-bio not installed")
seq = pytest.importorskip("treescape_connector.py_seq", reason="treescape_connector not built")
from skbio.sequence import distance as skd  # noqa: E402

REPORT_DIR = REPO / "tests" / "oracle" / "reports"
TOL = 1e-12
ORACLE = {"p": skd.pdist, "jc69": skd.jc69, "k2p": skd.k2p}
EXCLUDED: dict = {}


def _comparable(records) -> bool:
    """Aligned nucleotide input (unaligned and protein fixtures are the
    reference claim's business: scikit-bio cannot score them)."""
    try:
        return ref.validate(records)[2] == "nucleotide"
    except ref.SequenceError:
        return False


NUCLEOTIDE = [(a, r) for a, r in ALIGNMENTS if _comparable(r)]
CASES = [(a, r, m) for a, r in NUCLEOTIDE for m in ORACLE]


def _pairs(records):
    try:
        labels, seqs, _ = ref.validate(records, "nucleotide")
    except ref.SequenceError:
        return []
    return [((labels[i], seqs[i]), (labels[j], seqs[j])) for i in range(len(seqs)) for j in range(i + 1, len(seqs))]


@pytest.mark.parametrize("aid,records,model", CASES, ids=[f"{a}-{m}" for a, _, m in CASES])
def test_pairs_match_scikit_bio(aid, records, model) -> None:
    pairs = _pairs(records)
    assert pairs, f"{aid}: no pairs"
    checked = 0
    for (la, sa), (lb, sb) in pairs:
        theirs = ORACLE[model](skbio.DNA(sa), skbio.DNA(sb))
        if exact_boundary(sa, sb, "nucleotide", model) and theirs is not None and math.isfinite(theirs):
            EXCLUDED[f"{aid}/{model}:{la}-{lb}"] = f"exact {model} boundary; scikit-bio returns {theirs!r}"
            checked += 1
            continue
        for impl, fn in (
            ("reference", lambda: ref.pair_distance(sa, sb, "nucleotide", model, (la, lb))),
            ("rust", lambda: seq.distance_matrix([(la, sa), (lb, sb)], model, "nucleotide")[0][1]),
        ):
            try:
                ours = fn()
            except ValueError:
                ours = None
            if theirs is None or math.isnan(theirs):
                assert ours is None, f"{aid}/{model} {la}-{lb} ({impl}): scikit-bio NaN but treescape returned {ours}"
            else:
                assert ours is not None, f"{aid}/{model} {la}-{lb} ({impl}): treescape raised, scikit-bio {theirs}"
                assert abs(ours - theirs) < TOL, f"{aid}/{model} {la}-{lb} ({impl}): {ours} vs {theirs}"
        checked += 1
    assert checked == len(pairs)


@pytest.fixture(scope="session", autouse=True)
def _emit_report():
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-seq-distances-vs-scikit-bio",
        "version": "0.7",
        "timestamp_utc": int(time.time()),
        "alignments": [a for a, _ in NUCLEOTIDE],
        "models": list(ORACLE),
        "scikit_bio": skbio.__version__,
        "excluded_pairs": EXCLUDED,
        "tolerance": TOL,
    }
    (REPORT_DIR / "seq_distances_vs_oracles.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
