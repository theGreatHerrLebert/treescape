"""Oracle runner for claim ``treescape-seq-distances-rust-vs-reference``.

The Rust implementation (via ``treescape_connector.py_seq``) against
``treescape_reference.seq_distance`` on every alignment and every model:
matrices within 1e-12, and the same error message for every rejected
input. Protein models are also checked against hand-computed values.
"""

from __future__ import annotations

import json
import math
import time

import pytest

from _alignments import ALIGNMENTS
from _julia import REPO
from treescape_reference import seq_distance as ref

seq = pytest.importorskip("treescape_connector.py_seq", reason="treescape_connector not built")

REPORT_DIR = REPO / "tests" / "oracle" / "reports"
TOL = 1e-12
MODELS = ("p", "jc69", "k2p", "poisson")
ALPHABETS = ("auto", "nucleotide", "protein")
CASES = [(aid, recs, m, a) for aid, recs in ALIGNMENTS for m in MODELS for a in ALPHABETS]


def outcome_ref(records, model, alphabet):
    try:
        matrix, labels = ref.distance_matrix(records, model, alphabet)
        return ("ok", [v for row in matrix for v in row], labels)
    except ref.SequenceError as e:
        return ("error", str(e), None)


def outcome_rust(records, model, alphabet):
    try:
        flat, labels, _ = seq.distance_matrix(records, model, alphabet)
        return ("ok", flat, labels)
    except ValueError as e:
        return ("error", str(e), None)


@pytest.mark.parametrize("aid,records,model,alphabet", CASES, ids=[f"{a}-{m}-{al}" for a, _, m, al in CASES])
def test_rust_matches_reference(aid, records, model, alphabet) -> None:
    r, p = outcome_rust(records, model, alphabet), outcome_ref(records, model, alphabet)
    assert r[0] == p[0], f"{aid}/{model}: rust {r[0]} ({r[1] if r[0] == 'error' else ''}) vs reference {p[0]} ({p[1] if p[0] == 'error' else ''})"
    if r[0] == "error":
        assert r[1] == p[1], f"{aid}/{model}: messages differ\n rust: {r[1]}\n  ref: {p[1]}"
        return
    assert r[2] == p[2]
    for a, b in zip(r[1], p[1]):
        assert abs(a - b) < TOL and math.copysign(1, a) == math.copysign(1, b), f"{aid}/{model}: {a} vs {b}"


@pytest.mark.parametrize("aid,records", ALIGNMENTS, ids=[a for a, _ in ALIGNMENTS])
def test_doubtful_flag_matches_reference(aid, records) -> None:
    """The auto-detection warning fires for the same inputs in both."""
    try:
        _, seqs, alphabet = ref.validate(records)
    except ref.SequenceError:
        return
    try:
        _, _, doubtful = seq.distance_matrix(records, "p")
    except ValueError:
        return
    expected = alphabet == "nucleotide" and ref.auto_detection_is_doubtful(seqs)
    assert doubtful == expected, aid


def test_protein_models_match_their_formulas() -> None:
    """Hand-computed from the fixture: p1/p2 differ at 1 of 22 columns
    (column 22, Q/E); p1/p3 at 2 of 21 usable columns (columns 3, T/S,
    and 17, S/A; column 10 is a gap in p3 and is dropped)."""
    records = ref.read_fasta((REPO / "tests/fixtures/alignments/protein.fasta").read_text())
    for model, f in (
        ("p", lambda p: p),
        ("jc69", lambda p: -(19 / 20) * math.log(1 - p / (19 / 20))),
        ("poisson", lambda p: -math.log(1 - p)),
    ):
        flat, _, _ = seq.distance_matrix(records, model)
        n = 4
        assert abs(flat[0 * n + 1] - f(1 / 22)) < TOL, model
        assert abs(flat[0 * n + 2] - f(2 / 21)) < TOL, model


@pytest.fixture(scope="session", autouse=True)
def _emit_report():
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-seq-distances-rust-vs-reference",
        "version": "0.7",
        "timestamp_utc": int(time.time()),
        "alignments": [a for a, _ in ALIGNMENTS],
        "models": list(MODELS),
        "alphabets": list(ALPHABETS),
        "tolerance": TOL,
    }
    (REPORT_DIR / "seq_distances_vs_reference.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
