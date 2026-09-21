"""Shared harness for the sequence-distance claims (v0.7 Phase 2).

``ALIGNMENTS``: the simulated ``alignments-v1`` corpus
(``scripts/gen_alignments.py``) plus the hand-written FASTA fixtures in
``tests/fixtures/alignments/``, as ``(id, records)``.
"""

from __future__ import annotations

import sys

from _julia import REPO
from treescape_reference import seq_distance as ref
from treescape_reference.seq_distance import read_fasta

sys.path.insert(0, str(REPO / "scripts"))
from gen_alignments import corpus  # noqa: E402

FIXTURE_DIR = REPO / "tests" / "fixtures" / "alignments"
ALIGNMENTS = [(a.id, list(a.records)) for a in corpus()] + [
    (p.stem, read_fasta(p.read_text())) for p in sorted(FIXTURE_DIR.glob("*.fasta"))
]


def exact_boundary(a: str, b: str, alphabet: str, model: str) -> bool:
    """The pair sits exactly on a saturation boundary, decided on integer
    counts (JC69 ``k*d == (k-1)*L``; K2P ``L-2s-v == 0`` or ``L-2v == 0``).
    Floating-point oracles may return a finite value there while treescape
    raises (docs/conventions.md, disagreement log)."""
    definite = ref.NUCLEOTIDE_DEFINITE if alphabet == "nucleotide" else ref.PROTEIN_DEFINITE
    usable, s, v = ref._counts(a, b, definite)
    if usable == 0:
        return False
    if model == "jc69":
        k = 4 if alphabet == "nucleotide" else 20
        return k * (s + v) == (k - 1) * usable
    if model == "k2p":
        return usable - 2 * s - v == 0 or usable - 2 * v == 0
    return False
