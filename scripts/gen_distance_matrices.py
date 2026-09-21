"""The ``distance-v1`` corpus of distance matrices (tree-building claims).

    python scripts/gen_distance_matrices.py            # list the corpus
    python scripts/gen_distance_matrices.py --tsv DIR  # write it as TSV files

Matrices are derived, not stored: from each binary random tree with
positive branch lengths in ``tests/fixtures/trees/random/`` (the ``yule``,
``pda`` and ``ladder`` shapes) the script builds

* the **additive** matrix: path lengths between tips (patristic
  distances), for which neighbor joining must recover the tree; and
* a **noisy** matrix: each off-diagonal pair scaled by ``1 + e`` with
  ``e`` uniform in ``[-NOISE, NOISE]`` from a seeded stream per tree, so
  the matrix is no longer additive.

The source trees are pinned and hashed, and this script is part of the
corpus hash (``tests/fixtures/corpora.toml``), so every run and every
oracle sees the same matrices. Conventions: ``docs/conventions.md``.
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "tests" / "fixtures" / "trees" / "random"
SHAPES = ("yule", "pda", "ladder")
NOISE = 0.1
SEED = "treescape-distance-v1"

sys.path.insert(0, str(REPO / "packages" / "treescape-reference" / "src"))
from treescape_reference.newick import parse  # noqa: E402


@dataclass(frozen=True)
class Case:
    id: str  # e.g. "yule_016-additive"
    labels: tuple
    matrix: tuple  # tuple of row tuples
    source: str  # Newick of the generating tree
    additive: bool


def patristic(newick: str) -> tuple[list[str], list[list[float]]]:
    """Tip labels in pre-order and the path-length matrix between them."""
    tree = parse(newick)
    depth, path = {}, {}
    stack = [(tree.root, 0.0, ())]
    tips = []
    while stack:
        node, d, anc = stack.pop()
        here = anc + (id(node),)
        depth[id(node)] = d
        if node.is_tip():
            tips.append(node)
            path[id(node)] = here
        for child in reversed(node.children):
            stack.append((child, d + child.branch_length, here))
    n = len(tips)
    m = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            a, b = path[id(tips[i])], path[id(tips[j])]
            k = 0
            while k < min(len(a), len(b)) and a[k] == b[k]:
                k += 1
            lca = a[k - 1]
            v = (depth[id(tips[i])] - depth[lca]) + (depth[id(tips[j])] - depth[lca])
            m[i][j] = m[j][i] = v
    return [t.name for t in tips], m


def corpus() -> list[Case]:
    cases = []
    for path in sorted(SOURCE.glob("*.nwk")):
        if path.name.split("_")[0] not in SHAPES:
            continue
        newick = path.read_text()
        labels, m = patristic(newick)
        stem = path.stem
        cases.append(Case(f"{stem}-additive", tuple(labels), tuple(map(tuple, m)), newick, True))
        rng = random.Random(f"{SEED}:{stem}")
        n = len(labels)
        noisy = [row[:] for row in m]
        for i in range(n):
            for j in range(i + 1, n):
                noisy[i][j] = noisy[j][i] = m[i][j] * (1.0 + rng.uniform(-NOISE, NOISE))
        cases.append(Case(f"{stem}-noisy", tuple(labels), tuple(map(tuple, noisy)), newick, False))
    return cases


def to_tsv(case: Case) -> str:
    lines = ["\t".join(case.labels)]
    lines += ["\t".join(repr(v) for v in row) for row in case.matrix]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    cases = corpus()
    if argv[:1] == ["--tsv"] and len(argv) == 2:
        out = Path(argv[1])
        out.mkdir(parents=True, exist_ok=True)
        for case in cases:
            (out / f"{case.id}.tsv").write_text(to_tsv(case))
        print(f"wrote {len(cases)} matrices to {out}")
        return 0
    for case in cases:
        print(f"{case.id}\t{len(case.labels)} taxa")
    print(f"{len(cases)} matrices", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
