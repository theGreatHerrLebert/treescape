"""Oracle runner for claim ``treescape-seq-distances-vs-ape`` (release tier).

``workflow/scripts/oracle_seq_distance.R`` computes every comparable
alignment with R ape in one session: ``dist.dna`` (raw, JC69, K80; pairwise
deletion) for nucleotides, ``dist.aa`` (pairwise deletion, scaled) for the
protein p-distance. Compared pair by pair with both treescape
implementations within 1e-12; ape NaN/Inf must be a treescape error.

ape's ``dist.aa`` counts a gap as a difference even with pairwise
deletion (``docs/conventions.md``, disagreement log), and its handling of
the rarer protein codes (``B Z J U O *``) is not documented. Protein pairs
where either sequence has a gap or one of those codes are therefore
excluded by rule, listed in the report, and not sent to ape at all
(``read.FASTA(type = "AA")`` cannot read ``U``). ``.`` is written as ``-`` for
ape (both are gaps in treescape; ape's FASTA readers know only ``-``).

Like scikit-bio, ape can return a finite value (about 19-20) for a pair
exactly on the JC69 or K2P saturation boundary, where treescape raises.
Such a pair is excluded only when it is on the boundary by the integer
rule (``_alignments.exact_boundary``) and ape's value is finite, and it is
listed in the report.
"""

from __future__ import annotations

import functools
import json
import math
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

from _alignments import ALIGNMENTS, exact_boundary
from _julia import REPO
from _release import require
from treescape_reference import seq_distance as ref

REPORT_DIR = REPO / "tests" / "oracle" / "reports"
SCRIPT = REPO / "workflow" / "scripts" / "oracle_seq_distance.R"
TOL = 1e-12
MODEL = {"raw": "p", "JC69": "jc69", "K80": "k2p", "aa-p": "p"}
EXCLUDED: dict = {}
PASSED: list = []


def _comparable():
    out = []
    for aid, records in ALIGNMENTS:
        try:
            labels, seqs, alphabet = ref.validate(records)
        except ref.SequenceError:
            continue
        out.append((aid, labels, seqs, alphabet))
    return out


CASES = _comparable()


@functools.cache
def _have_ape() -> bool:
    import shutil

    if shutil.which("Rscript") is None:
        return False
    probe = subprocess.run(["Rscript", "-e", 'cat(requireNamespace("ape", quietly=TRUE))'], capture_output=True, text=True)
    return probe.stdout.strip() == "TRUE"


@functools.cache
def ape_version() -> str:
    out = subprocess.run(["Rscript", "-e", 'cat(as.character(packageVersion("ape")))'], capture_output=True, text=True)
    return out.stdout.strip()


PROTEIN_EXCLUDED = ref.GAPS | frozenset("BZJUO*")


def _sent_to_ape(seqs, alphabet) -> list:
    """Indices of the sequences ape sees. A protein sequence with a gap or
    one of ``B Z J U O *`` is excluded from every pair by rule, so it is
    not sent (ape's ``read.FASTA(type = "AA")`` cannot even read ``U``)."""
    if alphabet == "nucleotide":
        return list(range(len(seqs)))
    return [k for k, s in enumerate(seqs) if not set(s) & PROTEIN_EXCLUDED]


@functools.cache
def ape_results() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        for aid, _, seqs, alphabet in CASES:
            kept = _sent_to_ape(seqs, alphabet)
            if len(kept) < 2:
                continue
            kind = "dna" if alphabet == "nucleotide" else "aa"
            (Path(tmp) / f"{aid}.{kind}.fasta").write_text(
                "".join(f">{k}\n{seqs[k].replace('.', '-')}\n" for k in kept)
            )
        run = subprocess.run(["Rscript", str(SCRIPT), tmp], capture_output=True, text=True)
        if run.returncode != 0:
            raise RuntimeError(f"{SCRIPT.name} failed:\n{run.stderr}")
    results = {}
    for line in run.stdout.splitlines():
        aid, model, n, values = line.split("\t")
        results[(aid, MODEL[model])] = (int(n), [float(v) for v in values.split(",")])
    return results


@pytest.mark.release_only
@pytest.mark.parametrize("aid,labels,seqs,alphabet", CASES, ids=[c[0] for c in CASES])
def test_pairs_match_ape(aid, labels, seqs, alphabet) -> None:
    require(_have_ape(), "R with ape")
    seq = pytest.importorskip("treescape_connector.py_seq", reason="treescape_connector not built")
    kept = _sent_to_ape(seqs, alphabet)
    kept_set = set(kept)
    for i in range(len(seqs)):
        for j in range(i + 1, len(seqs)):
            if i not in kept_set or j not in kept_set:
                EXCLUDED[f"{aid}:{labels[i]}-{labels[j]}"] = "protein pair with a gap or one of B Z J U O *"
    if len(kept) < 2:
        PASSED.append(aid)
        return
    models = ("p", "jc69", "k2p") if alphabet == "nucleotide" else ("p",)
    for model in models:
        n, values = ape_results()[(aid, model)]
        assert n == len(kept)
        for a in range(n):
            for b in range(a + 1, n):
                i, j = kept[a], kept[b]
                theirs = values[a * n + b]
                if exact_boundary(seqs[i], seqs[j], alphabet, model) and math.isfinite(theirs):
                    EXCLUDED[f"{aid}/{model}:{labels[i]}-{labels[j]}"] = f"exact {model} boundary; ape returns {theirs!r}"
                    continue
                for impl, fn in (
                    ("reference", lambda: ref.pair_distance(seqs[i], seqs[j], alphabet, model, (labels[i], labels[j]))),
                    ("rust", lambda: seq.distance_matrix([(labels[i], seqs[i]), (labels[j], seqs[j])], model, alphabet)[0][1]),
                ):
                    try:
                        ours = fn()
                    except ValueError:
                        ours = None
                    if math.isnan(theirs) or math.isinf(theirs):
                        assert ours is None, f"{aid}/{model} {labels[i]}-{labels[j]} ({impl}): ape {theirs}, treescape {ours}"
                    else:
                        assert ours is not None, f"{aid}/{model} {labels[i]}-{labels[j]} ({impl}): treescape raised, ape {theirs}"
                        assert abs(ours - theirs) < TOL, f"{aid}/{model} {labels[i]}-{labels[j]} ({impl}): {ours} vs ape {theirs}"
    PASSED.append(aid)


@pytest.fixture(scope="session", autouse=True)
def _emit_report():
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-seq-distances-vs-ape",
        "version": "0.7",
        "timestamp_utc": int(time.time()),
        "alignments": [c[0] for c in CASES],
        "ape": ape_version() if _have_ape() else None,
        "excluded_pairs": EXCLUDED,
        "passed": PASSED,
        "all_passed": len(PASSED) == len(CASES),
        "tolerance": TOL,
    }
    (REPORT_DIR / "seq_distances_vs_ape.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
