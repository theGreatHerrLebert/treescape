"""Trees from distance matrices: neighbor joining and UPGMA.

The convention owner for ``treescape-core::tree_build``. Every step —
the active list, the tie rule, the floating-point order of every sum —
is pinned in ``docs/conventions.md``, "Trees from distance matrices",
so the Rust port builds the same tree, ties included.

Plain Python on purpose: the arithmetic is written out step by step so a
reader can check it against the textbook, and so no library's summation
or tie-breaking leaks in.
"""

from __future__ import annotations

import math
from typing import Callable, List, Optional, Sequence

from treescape_reference.newick import Node, Tree

SYMMETRY_TOL = 1e-9


class DistanceMatrixError(ValueError):
    """The matrix or its labels violate the input rules."""


def validate(matrix: Sequence[Sequence[float]], labels: Sequence[str]) -> List[List[float]]:
    """Check the input rules and return the matrix as a list of float rows."""
    n = len(matrix)
    if n < 2:
        raise DistanceMatrixError(f"need at least 2 taxa, got {n}")
    if len(labels) != n:
        raise DistanceMatrixError(f"{len(labels)} labels for a {n} x {n} matrix")
    rows: List[List[float]] = []
    for i, row in enumerate(matrix):
        if len(row) != n:
            raise DistanceMatrixError(f"row {i} has {len(row)} entries; the matrix is not square ({n} rows)")
        rows.append([float(v) for v in row])
    for i in range(n):
        for j in range(n):
            v = rows[i][j]
            if not math.isfinite(v):
                raise DistanceMatrixError(f"D[{i}][{j}] is not finite ({v})")
            if v < 0:
                raise DistanceMatrixError(f"D[{i}][{j}] is negative ({v})")
        if rows[i][i] != 0.0:
            raise DistanceMatrixError(f"D[{i}][{i}] is {rows[i][i]}; the diagonal must be 0")
    for i in range(n):
        for j in range(i + 1, n):
            a, b = rows[i][j], rows[j][i]
            if abs(a - b) > SYMMETRY_TOL * max(1.0, abs(a)):
                raise DistanceMatrixError(f"D[{i}][{j}] = {a} but D[{j}][{i}] = {b}; the matrix is not symmetric")
    _validate_labels(labels)
    return rows


def _validate_labels(labels: Sequence[str]) -> None:
    seen = set()
    for i, label in enumerate(labels):
        if not isinstance(label, str) or not label:
            raise DistanceMatrixError(f"label {i} must be a non-empty string, got {label!r}")
        if label in seen:
            raise DistanceMatrixError(f"duplicate label {label!r}")
        seen.add(label)


def _upper(rows: List[List[float]]) -> List[List[float]]:
    """Symmetric working copy built from the upper triangle only."""
    n = len(rows)
    d = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d[i][j] = d[j][i] = rows[i][j]
    return d


def _join(children: List[Node], lengths: List[float]) -> Node:
    node = Node()
    for child, length in zip(children, lengths):
        child.branch_length = length
        child.parent = node
        node.children.append(child)
    return node


def _tips(node: Node) -> frozenset:
    out, stack = set(), [node]
    while stack:
        n = stack.pop()
        if n.is_tip():
            out.add(n.name)
        stack.extend(n.children)
    return frozenset(out)


def _pair(matrix: List[List[float]], labels: Sequence[str]) -> Tree:
    a, b = Node(name=labels[0]), Node(name=labels[1])
    half = matrix[0][1] / 2
    return Tree(root=_join([a, b], [half, half]))


StepHook = Optional[Callable[[int, List[tuple]], None]]


def neighbor_joining(matrix: Sequence[Sequence[float]], labels: Sequence[str], *, on_step: StepHook = None) -> Tree:
    """Neighbor joining (Saitou & Nei 1987, Studier & Keppler criterion).

    ``on_step(r, candidates)`` is called before every join with the number
    of active clusters and every candidate ``(value, label_set_p,
    label_set_q)``; oracle runners use it to prove a matrix has no ties
    that could change the tree. The candidates are built only when a hook
    is given.
    """
    rows = validate(matrix, labels)
    if len(rows) == 2:
        return _pair(rows, labels)
    d = _upper(rows)
    # Active list: positions into `nodes` / `dist` rows, in list order.
    nodes: List[Node] = [Node(name=label) for label in labels]
    # Distances between active clusters, keyed by cluster id (index into
    # `nodes`); new clusters get new ids, so rows only ever grow.
    dist: dict = {i: {j: d[i][j] for j in range(len(rows)) if j != i} for i in range(len(rows))}
    active: List[int] = list(range(len(rows)))

    while len(active) > 3:
        r = len(active)
        total = {}
        for k in active:
            s = 0.0
            for m in active:
                if m != k:
                    s += dist[k][m]
            total[k] = s
        best = None
        candidates = []
        tips = {k: _tips(nodes[k]) for k in active} if on_step is not None else {}
        for pi in range(r):
            for qi in range(pi + 1, r):
                p, q = active[pi], active[qi]
                value = (r - 2) * dist[p][q] - total[p] - total[q]
                if best is None or value < best[0]:
                    best = (value, pi, qi)
                if on_step is not None:
                    candidates.append((value, tips[p], tips[q]))
        if on_step is not None:
            on_step(r, candidates)
        _, pi, qi = best
        p, q = active[pi], active[qi]
        dpq = dist[p][q]
        dp = dpq / 2 + (total[p] - total[q]) / (2 * (r - 2))
        dq = dpq - dp
        u = len(nodes)
        nodes.append(_join([nodes[p], nodes[q]], [dp, dq]))
        dist[u] = {}
        for k in active:
            if k != p and k != q:
                duk = (dist[p][k] + dist[q][k] - dpq) / 2
                dist[u][k] = duk
                dist[k][u] = duk
        active = [k for k in active if k != p and k != q] + [u]

    a, b, c = active
    dab, dac, dbc = dist[a][b], dist[a][c], dist[b][c]
    root = _join(
        [nodes[a], nodes[b], nodes[c]],
        [(dab + dac - dbc) / 2, (dab + dbc - dac) / 2, (dac + dbc - dab) / 2],
    )
    return Tree(root=root)


def upgma(matrix: Sequence[Sequence[float]], labels: Sequence[str], *, on_step: StepHook = None) -> Tree:
    """UPGMA: average linkage weighted by cluster size (Sokal & Michener 1958).

    ``on_step`` as in :func:`neighbor_joining`.
    """
    rows = validate(matrix, labels)
    if len(rows) == 2:
        return _pair(rows, labels)
    d = _upper(rows)
    n = len(rows)
    nodes: List[Node] = [Node(name=label) for label in labels]
    height = [0.0] * n
    size = [1] * n
    dist: dict = {i: {j: d[i][j] for j in range(n) if j != i} for i in range(n)}
    active: List[int] = list(range(n))

    while len(active) > 1:
        r = len(active)
        best = None
        candidates = []
        tips = {k: _tips(nodes[k]) for k in active} if on_step is not None else {}
        for pi in range(r):
            for qi in range(pi + 1, r):
                value = dist[active[pi]][active[qi]]
                if best is None or value < best[0]:
                    best = (value, pi, qi)
                if on_step is not None:
                    candidates.append((value, tips[active[pi]], tips[active[qi]]))
        if on_step is not None:
            on_step(r, candidates)
        dpq, pi, qi = best
        p, q = active[pi], active[qi]
        h = dpq / 2
        u = len(nodes)
        nodes.append(_join([nodes[p], nodes[q]], [h - height[p], h - height[q]]))
        height.append(h)
        size.append(size[p] + size[q])
        dist[u] = {}
        for k in active:
            if k != p and k != q:
                duk = (size[p] * dist[p][k] + size[q] * dist[q][k]) / (size[p] + size[q])
                dist[u][k] = duk
                dist[k][u] = duk
        active = [k for k in active if k != p and k != q] + [u]

    root = nodes[active[0]]
    root.branch_length = 0.0
    return Tree(root=root)


def from_linkage(linkage: Sequence[Sequence[float]], labels: Sequence[str]) -> Tree:
    """Tree from a SciPy linkage matrix; node height = merge distance / 2.

    Each cluster (a tip, or an earlier row) must be joined exactly once;
    a matrix that reuses one would drop or duplicate tips, so it is an
    error.
    """
    n = len(labels)
    if n < 2 or len(linkage) != n - 1:
        raise DistanceMatrixError(f"a linkage matrix for {n} labels has {max(n - 1, 0)} rows, got {len(linkage)}")
    _validate_labels(labels)
    nodes: List[Node] = [Node(name=label) for label in labels]
    height = [0.0] * n
    used = [False] * (2 * n - 1)
    for i, row in enumerate(linkage):
        a, b, dist = float(row[0]), float(row[1]), float(row[2])
        valid = lambda x: math.isfinite(x) and x == int(x) and 0 <= x < n + i  # noqa: E731
        if not (valid(a) and valid(b)) or a == b or used[int(a)] or used[int(b)]:
            raise DistanceMatrixError(f"linkage row {i} joins invalid clusters")
        a, b = int(a), int(b)
        used[a] = used[b] = True
        if not math.isfinite(dist) or dist < 0:
            raise DistanceMatrixError(f"linkage row {i} has invalid distance {row[2]!r}")
        h = dist / 2
        nodes.append(_join([nodes[a], nodes[b]], [h - height[a], h - height[b]]))
        height.append(h)
    root = nodes[-1]
    root.branch_length = 0.0
    return Tree(root=root)


__all__ = ["DistanceMatrixError", "from_linkage", "neighbor_joining", "upgma", "validate"]
