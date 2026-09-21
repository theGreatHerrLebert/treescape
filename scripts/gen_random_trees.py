"""Generate the pinned random layout corpus (``tests/fixtures/trees/random/``).

    python scripts/gen_random_trees.py          # (re)write the corpus
    python scripts/gen_random_trees.py --check  # exit 1 if files differ

Rules (seed, sizes, shapes, branch lengths, names) are pinned in
``docs/conventions.md`` under "Layout oracle corpus and node-level
comparison". The files are checked in; claims hash them through the
``layout-v2`` corpus in ``tests/fixtures/corpora.toml``, so this script
only ever reproduces them.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "tests" / "fixtures" / "trees" / "random"

SEED = 20260921
SIZES = [3, 4, 5, 7, 10, 16, 25, 40, 64, 100, 150, 200]
SHAPES = ["yule", "pda", "ladder", "polytomy", "zeros"]
MEAN_BRANCH = 0.1
COLLAPSE_P = 0.3
ZERO_P = 0.2


class Node:
    def __init__(self) -> None:
        self.children: list[Node] = []
        self.name = ""
        self.length: float | None = None


def _tips(root: Node) -> list[Node]:
    out, stack = [], [root]
    while stack:
        n = stack.pop()
        if n.children:
            stack.extend(reversed(n.children))
        else:
            out.append(n)
    return out


def _preorder(root: Node) -> list[Node]:
    out, stack = [], [root]
    while stack:
        n = stack.pop()
        out.append(n)
        stack.extend(reversed(n.children))
    return out


def _cherry() -> Node:
    root = Node()
    root.children = [Node(), Node()]
    return root


def yule(rng: random.Random, n: int) -> Node:
    root = _cherry()
    while len(_tips(root)) < n:
        tip = rng.choice(_tips(root))
        tip.children = [Node(), Node()]
    return root


def pda(rng: random.Random, n: int) -> Node:
    root = _cherry()
    count = 2
    while count < n:
        # Edges are identified by their lower node; `None` is the edge above the root.
        edges: list[Node | None] = [None] + _preorder(root)[1:]
        target = rng.choice(edges)
        if target is None:
            new_root = Node()
            new_root.children = [root, Node()]
            root = new_root
        else:
            parent = next(p for p in _preorder(root) if target in p.children)
            joint = Node()
            joint.children = [target, Node()]
            parent.children[parent.children.index(target)] = joint
        count += 1
    return root


def ladder(_rng: random.Random, n: int) -> Node:
    root = _cherry()
    for _ in range(n - 2):
        top = Node()
        top.children = [root, Node()]
        root = top
    return root


def polytomy(rng: random.Random, n: int) -> Node:
    """``yule``, then each internal edge collapsed once with probability
    ``COLLAPSE_P``: one bottom-up pass, every edge tested exactly once."""
    root = yule(rng, n)
    parent = {id(c): p for p in _preorder(root) for c in p.children}
    internal = [node for node in _preorder(root)[1:] if node.children]
    for node in reversed(internal):  # children before parents
        if rng.random() < COLLAPSE_P:
            up = parent[id(node)]
            i = up.children.index(node)
            up.children[i : i + 1] = node.children
            for c in node.children:
                parent[id(c)] = up
    return root


def _decorate(rng: random.Random, root: Node, zero_p: float) -> None:
    for i, tip in enumerate(_tips(root), start=1):
        tip.name = f"t{i:03d}"
    for node in _preorder(root)[1:]:
        length = round(rng.expovariate(1.0 / MEAN_BRANCH), 6)
        node.length = 0.0 if zero_p and rng.random() < zero_p else length


def to_newick(root: Node) -> str:
    def emit(n: Node) -> str:
        inner = "(" + ",".join(emit(c) for c in n.children) + ")" if n.children else n.name
        return inner if n.length is None else f"{inner}:{n.length!r}"

    return emit(root) + ";\n"


def corpus() -> dict[str, str]:
    rng = random.Random(SEED)
    out: dict[str, str] = {}
    for shape in SHAPES:
        for n in SIZES:
            builder = {"yule": yule, "pda": pda, "ladder": ladder, "polytomy": polytomy, "zeros": yule}[shape]
            root = builder(rng, n)
            _decorate(rng, root, ZERO_P if shape == "zeros" else 0.0)
            assert len(_tips(root)) == n
            out[f"{shape}_{n:03d}.nwk"] = to_newick(root)
    return out


def main(argv: list[str]) -> int:
    files = corpus()
    if argv == ["--check"]:
        on_disk = {p.name: p.read_text() for p in OUT.glob("*.nwk")}
        if on_disk != files:
            print("random corpus differs from the generator; run scripts/gen_random_trees.py", file=sys.stderr)
            return 1
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*.nwk"):
        if stale.name not in files:
            stale.unlink()
    for name, text in files.items():
        (OUT / name).write_text(text)
    print(f"wrote {len(files)} trees to {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
