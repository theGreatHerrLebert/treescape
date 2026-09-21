"""Distances from aligned sequences: p, Jukes–Cantor, Kimura 2-parameter, Poisson.

The convention owner for ``treescape-core::seq_distance``
(``docs/conventions.md``, "Distances from aligned sequences"). Written
out step by step so each formula can be checked against its reference.
"""

from __future__ import annotations

import math
from typing import List, Sequence, Tuple

NUCLEOTIDE_DEFINITE = frozenset("ACGT")
NUCLEOTIDE_AMBIGUOUS = frozenset("NRYSWKMBDHV")
PROTEIN_DEFINITE = frozenset("ACDEFGHIKLMNPQRSTVWY")
PROTEIN_AMBIGUOUS = frozenset("XBZJUO*")
GAPS = frozenset("-.")
PURINES = frozenset("AG")
PYRIMIDINES = frozenset("CT")
MODELS = {"nucleotide": ("p", "jc69", "k2p"), "protein": ("p", "jc69", "poisson")}


class SequenceError(ValueError):
    """The sequences or the model violate the input rules."""


# FASTA whitespace: ASCII only (docs/conventions.md).
WHITESPACE = " \t\r\v\f"


def read_fasta(text: str) -> List[Tuple[str, str]]:
    """``[(label, sequence)]`` from FASTA text (lines split on ``\\n``, a
    trailing ``\\r`` dropped, ASCII whitespace only)."""
    records: List[Tuple[str, List[str]]] = []
    for number, raw in enumerate(text.split("\n"), start=1):
        line = raw[:-1] if raw.endswith("\r") else raw
        line = line.strip(WHITESPACE)
        if not line:
            continue
        if line.startswith(">"):
            words = [w for w in _split_ascii(line[1:]) if w]
            if not words:
                raise SequenceError(f"FASTA line {number}: empty header")
            records.append((words[0], []))
        else:
            if not records:
                raise SequenceError(f"FASTA line {number}: sequence data before the first '>' header")
            records[-1][1].append("".join(c for c in line if c not in WHITESPACE))
    return [(label, "".join(parts)) for label, parts in records]


def _split_ascii(text: str) -> List[str]:
    out, word = [], []
    for c in text:
        if c in WHITESPACE:
            out.append("".join(word))
            word = []
        else:
            word.append(c)
    out.append("".join(word))
    return out


def is_fasta_text(source: str) -> bool:
    """A string that starts with '>' (after ASCII whitespace) is FASTA text."""
    return source.lstrip(WHITESPACE + "\n").startswith(">")


def detect_alphabet(seqs: Sequence[str]) -> str:
    """On uppercased sequences (``U`` still ``U``)."""
    nucleotide = NUCLEOTIDE_DEFINITE | NUCLEOTIDE_AMBIGUOUS | GAPS | {"U"}
    return "nucleotide" if all(set(s) <= nucleotide for s in seqs) else "protein"


def auto_detection_is_doubtful(seqs: Sequence[str]) -> bool:
    """Auto chose nucleotide, but more than half of the non-gap characters
    are nucleotide ambiguity codes (docs/conventions.md: warn)."""
    total = ambiguous = 0
    for s in seqs:
        for c in s:
            if c in GAPS:
                continue
            total += 1
            ambiguous += c in NUCLEOTIDE_AMBIGUOUS
    return total > 0 and 2 * ambiguous > total


def validate(records: Sequence[Tuple[str, str]], alphabet: str = "auto") -> Tuple[List[str], List[str], str]:
    """Check the input rules; return labels, normalized sequences, alphabet."""
    if len(records) < 2:
        raise SequenceError(f"need at least 2 sequences, got {len(records)}")
    labels = [label for label, _ in records]
    seen = set()
    for i, label in enumerate(labels):
        if not isinstance(label, str) or not label:
            raise SequenceError(f"label {i} must be a non-empty string, got {label!a}")
        if label in seen:
            raise SequenceError(f"duplicate label {label!a}")
        seen.add(label)
    for label, seq in records:
        if not isinstance(seq, str):
            raise SequenceError(f"sequence {label!a} must be a string, got {type(seq).__name__}")
        for column, char in enumerate(seq, start=1):
            if ord(char) > 127:
                raise SequenceError(f"sequence {label!a} has {char!a} at column {column}; sequences must be ASCII")
    seqs = [seq.upper() for _, seq in records]
    length = len(seqs[0])
    for label, seq in zip(labels, seqs):
        if len(seq) != length:
            raise SequenceError(
                f"sequence {label!a} has length {len(seq)}, but {labels[0]!a} has {length}; "
                "the sequences must be aligned (use MAFFT, MUSCLE or Clustal Omega first)"
            )
    if alphabet == "auto":
        alphabet = detect_alphabet(seqs)
    elif alphabet not in MODELS:
        raise SequenceError(f"alphabet must be 'auto', 'nucleotide' or 'protein', got {alphabet!a}")
    if alphabet == "nucleotide":
        seqs = [seq.replace("U", "T") for seq in seqs]
    allowed = (
        NUCLEOTIDE_DEFINITE | NUCLEOTIDE_AMBIGUOUS
        if alphabet == "nucleotide"
        else PROTEIN_DEFINITE | PROTEIN_AMBIGUOUS
    ) | GAPS
    for label, seq in zip(labels, seqs):
        for column, char in enumerate(seq, start=1):
            if char not in allowed:
                raise SequenceError(f"sequence {label!a} has {char!a} at column {column}, not a {alphabet} character")
    return labels, seqs, alphabet


def _counts(a: str, b: str, definite: frozenset) -> Tuple[int, int, int]:
    """Usable columns, transitions, other differences (pairwise deletion)."""
    usable = transitions = other = 0
    for x, y in zip(a, b):
        if x not in definite or y not in definite:
            continue
        usable += 1
        if x == y:
            continue
        if (x in PURINES and y in PURINES) or (x in PYRIMIDINES and y in PYRIMIDINES):
            transitions += 1
        else:
            other += 1
    return usable, transitions, other


def pair_distance(a: str, b: str, alphabet: str, model: str, names: Tuple[str, str] = ("a", "b")) -> float:
    definite = NUCLEOTIDE_DEFINITE if alphabet == "nucleotide" else PROTEIN_DEFINITE
    usable, transitions, other = _counts(a, b, definite)
    pair = f"{names[0]!a} and {names[1]!a}"
    if usable == 0:
        raise SequenceError(f"{pair} share no column where both have a definite character")
    diffs = transitions + other
    if diffs == 0 and model in ("p", "jc69", "k2p", "poisson"):
        # Every correction is -c * ln(1) = -0.0 here; identical sequences
        # are at distance +0.0 (docs/conventions.md).
        return 0.0
    p = diffs / usable
    if model == "p":
        return p
    # Saturation is decided on exact integer counts (docs/conventions.md).
    if model == "jc69":
        k = 4 if alphabet == "nucleotide" else 20
        b_ = (k - 1) / k
        if k * diffs >= (k - 1) * usable:
            raise SequenceError(f"{pair}: p = {p} is saturated for jc69 (needs p < {b_})")
        return -b_ * math.log(1 - p / b_)
    if model == "k2p":
        n1 = usable - 2 * transitions - other
        n2 = usable - 2 * other
        if n1 <= 0 or n2 <= 0:
            raise SequenceError(
                f"{pair}: P = {transitions / usable}, Q = {other / usable} are saturated for k2p"
            )
        return -0.5 * math.log(n1 / usable) - 0.25 * math.log(n2 / usable)
    if model == "poisson":
        if diffs >= usable:
            raise SequenceError(f"{pair}: p = {p} is saturated for poisson (needs p < 1)")
        return -math.log(1 - p)
    raise SequenceError(f"unknown model {model!a}")


def distance_matrix(
    records: Sequence[Tuple[str, str]], model: str = "jc69", alphabet: str = "auto"
) -> Tuple[List[List[float]], List[str]]:
    """Pairwise distances (upper triangle computed, then mirrored) and labels."""
    labels, seqs, alphabet = validate(records, alphabet)
    if model not in MODELS[alphabet]:
        raise SequenceError(f"model {model!a} is not available for {alphabet} sequences (choose from {MODELS[alphabet]})")
    n = len(seqs)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = pair_distance(seqs[i], seqs[j], alphabet, model, (labels[i], labels[j]))
            matrix[i][j] = matrix[j][i] = d
    return matrix, labels


__all__ = [
    "SequenceError",
    "auto_detection_is_doubtful",
    "detect_alphabet",
    "distance_matrix",
    "is_fasta_text",
    "pair_distance",
    "read_fasta",
    "validate",
]
