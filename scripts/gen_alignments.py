"""The ``alignments-v1`` corpus of aligned sequences (sequence-distance claims).

    python scripts/gen_alignments.py              # list the corpus
    python scripts/gen_alignments.py --fasta DIR  # write it as FASTA files

Sequences are simulated along the pinned random trees
(``tests/fixtures/trees/random/``, shapes ``yule``, ``pda`` and ``ladder``,
3 to 64 tips): a random root sequence of ``LENGTH`` sites evolves down
each branch under JC69 or K2P (transition/transversion ratio ``KAPPA``).
Afterwards each site of each sequence becomes a gap with probability
``GAP_P`` or ``N`` with probability ``N_P``, so pairwise deletion is always
exercised. Everything is seeded; like ``distance-v1`` the corpus is
derived, not stored, and this script is part of its hash.
"""

from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "tests" / "fixtures" / "trees" / "random"
SHAPES = ("yule", "pda", "ladder")
MAX_TIPS = 64
LENGTH = 300
KAPPA = 2.0
GAP_P = 0.03
N_P = 0.01
SEED = "treescape-alignments-v1"

sys.path.insert(0, str(REPO / "packages" / "treescape-reference" / "src"))
from treescape_reference.newick import parse  # noqa: E402

PURINE = {"A": "G", "G": "A", "C": "T", "T": "C"}  # transition partner


@dataclass(frozen=True)
class Alignment:
    id: str  # e.g. "yule_016-k2p"
    records: tuple  # ((label, sequence), ...)


def _mutate(base: str, t: float, model: str, rng: random.Random) -> str:
    """One site after branch length ``t`` (expected substitutions per site)."""
    if model == "jc69":
        # P(change) = 3/4 (1 - e^{-4t/3}); the new base is uniform among the other three.
        if rng.random() < 0.75 * (1 - math.exp(-4 * t / 3)):
            return rng.choice([b for b in "ACGT" if b != base])
        return base
    # K2P with ratio KAPPA: rates alpha (transition) and beta (each transversion),
    # scaled so that alpha + 2 beta = 1 substitution per unit t.
    beta = 1 / (KAPPA + 2)
    alpha = KAPPA * beta
    p_transversion = 0.5 * (1 - math.exp(-4 * beta * t))
    p_transition = 0.25 + 0.25 * math.exp(-4 * beta * t) - 0.5 * math.exp(-2 * (alpha + beta) * t)
    u = rng.random()
    if u < p_transition:
        return PURINE[base]
    if u < p_transition + p_transversion:
        return rng.choice([b for b in "ACGT" if b not in (base, PURINE[base])])
    return base


def simulate(newick: str, model: str, rng: random.Random) -> list[tuple[str, str]]:
    tree = parse(newick)
    root = [rng.choice("ACGT") for _ in range(LENGTH)]
    out, stack = [], [(tree.root, root)]
    while stack:
        node, seq = stack.pop()
        if node.is_tip():
            out.append((node.name, seq))
        for child in reversed(node.children):
            stack.append((child, [_mutate(b, child.branch_length, model, rng) for b in seq]))
    records = []
    for name, seq in sorted(out):
        chars = ["-" if rng.random() < GAP_P else ("N" if rng.random() < N_P else b) for b in seq]
        records.append((name, "".join(chars)))
    return records


def corpus() -> list[Alignment]:
    cases = []
    for path in sorted(SOURCE.glob("*.nwk")):
        shape, size = path.stem.split("_")
        if shape not in SHAPES or int(size) > MAX_TIPS:
            continue
        for model in ("jc69", "k2p"):
            rng = random.Random(f"{SEED}:{path.stem}:{model}")
            cases.append(Alignment(f"{path.stem}-{model}", tuple(simulate(path.read_text(), model, rng))))
    return cases


def main(argv: list[str]) -> int:
    cases = corpus()
    if argv[:1] == ["--fasta"] and len(argv) == 2:
        out = Path(argv[1])
        out.mkdir(parents=True, exist_ok=True)
        for case in cases:
            (out / f"{case.id}.fasta").write_text("".join(f">{n}\n{s}\n" for n, s in case.records))
        print(f"wrote {len(cases)} alignments to {out}")
        return 0
    for case in cases:
        print(f"{case.id}\t{len(case.records)} sequences")
    print(f"{len(cases)} alignments", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
