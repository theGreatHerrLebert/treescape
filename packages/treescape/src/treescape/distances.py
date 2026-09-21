"""Distances from aligned sequences (``docs/conventions.md``, "Distances from
aligned sequences").

    D, labels = distances.from_fasta("aligned.fasta", model="jc69")
    D, labels = distances.from_fasta_text(">a\\nACGT\\n>b\\nACGA\\n")
    D, labels = distances.from_records([("a", "ACGT..."), ("b", "ACGA...")], model="k2p")

``D`` is a list of rows ready for :meth:`treescape.TreePlot.from_distances`.

Models: ``"p"``, ``"jc69"`` (4 states for nucleotides, 20 for proteins),
``"k2p"`` (nucleotides) and ``"poisson"`` (proteins). Gaps and ambiguity
codes are removed pair by pair. The sequences must already be aligned.

``alphabet="auto"`` treats sequences made only of nucleotide codes as
nucleotides. A short protein can consist only of such letters (``M``,
``K``, ``W``, ``R``… are also nucleotide ambiguity codes); when that looks
likely, a :class:`TreescapeSequenceWarning` suggests ``alphabet="protein"``.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import List, Mapping, Sequence, Tuple, Union

from treescape_connector import py_seq as _seq

Records = Union[Sequence[Tuple[str, str]], Mapping[str, str]]


class TreescapeSequenceWarning(UserWarning):
    """Auto-detection chose nucleotide for sequences that look like protein."""


def read_fasta(path: Union[str, Path]) -> List[Tuple[str, str]]:
    """``[(label, sequence)]`` from a FASTA file."""
    # newline="": no newline translation, so a bare \r is not a line break
    # (docs/conventions.md, "FASTA"), exactly as Julia reads the same file.
    with open(path, encoding="utf-8", newline="") as f:
        return _seq.read_fasta(f.read())


def read_fasta_text(text: str) -> List[Tuple[str, str]]:
    """``[(label, sequence)]`` from FASTA text."""
    return _seq.read_fasta(text)


def from_records(
    records: Records, model: str = "jc69", alphabet: str = "auto"
) -> Tuple[List[List[float]], List[str]]:
    """Distance matrix (list of rows) and labels from ``(label, sequence)``
    pairs or a ``{label: sequence}`` mapping."""
    pairs = list(records.items()) if isinstance(records, Mapping) else list(records)
    for i, pair in enumerate(pairs):
        if not (isinstance(pair, tuple) or isinstance(pair, list)) or len(pair) != 2:
            raise TypeError(f"record {i} must be a (label, sequence) pair, got {pair!r}")
        label, seq = pair
        if not isinstance(label, str) or not isinstance(seq, str):
            raise TypeError(
                f"record {i}: label and sequence must be str, got {type(label).__name__} and {type(seq).__name__}"
            )
    flat, labels, doubtful = _seq.distance_matrix([tuple(p) for p in pairs], model, alphabet)
    if doubtful:
        warnings.warn(
            "alphabet='auto' treated these sequences as nucleotides, but most of their letters are "
            "nucleotide ambiguity codes; if they are proteins, pass alphabet='protein'",
            TreescapeSequenceWarning,
            stacklevel=2,
        )
    n = len(labels)
    return [flat[i * n : (i + 1) * n] for i in range(n)], labels


def from_fasta(
    path: Union[str, Path], model: str = "jc69", alphabet: str = "auto"
) -> Tuple[List[List[float]], List[str]]:
    """Distance matrix (list of rows) and labels from an aligned FASTA file."""
    return from_records(read_fasta(path), model=model, alphabet=alphabet)


def from_fasta_text(text: str, model: str = "jc69", alphabet: str = "auto") -> Tuple[List[List[float]], List[str]]:
    """Distance matrix (list of rows) and labels from aligned FASTA text."""
    return from_records(read_fasta_text(text), model=model, alphabet=alphabet)


def from_source(source, model: str = "jc69", alphabet: str = "auto") -> Tuple[List[List[float]], List[str]]:
    """``source`` is FASTA text (a string starting with ``>``), a path, a
    ``{label: sequence}`` mapping, or ``(label, sequence)`` pairs."""
    if isinstance(source, str) and _seq.is_fasta_text(source):
        return from_fasta_text(source, model=model, alphabet=alphabet)
    if isinstance(source, (str, Path)):
        return from_fasta(source, model=model, alphabet=alphabet)
    return from_records(source, model=model, alphabet=alphabet)


__all__ = [
    "TreescapeSequenceWarning",
    "from_fasta",
    "from_fasta_text",
    "from_records",
    "from_source",
    "read_fasta",
    "read_fasta_text",
]
