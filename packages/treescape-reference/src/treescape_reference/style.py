"""Reference styling resolution for :class:`treescape.TreePlot`.

Extracted from the v0.4 ``plot.py`` (v0.5 Phase 1) before the Rust port
in ``treescape-core/src/style.rs`` existed. This module is the readable
convention owner: the Rust resolver is held to it with exact equality
(claim ``treescape-style-resolution-rust-vs-reference``).

Inputs mirror the Rust boundary shape (docs/conventions.md, v0.5
Phase 1): ``tree`` is anything with ``preorder()``, ``root``,
``is_tip(i)``, ``name(i)``, ``children(i)`` and ``tip_order()`` (the
connector's ``Tree`` qualifies). Columns are lists aligned to
``tree.tip_order()``: ``Optional[float]`` for numeric, ``Optional[int]``
codes for discrete.

Host-side concerns — dataframes, dtype detection, color-string parsing,
callable cmaps, warning emission — are deliberately not here.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence


TABLEAU_10 = (
    "#4e79a7",
    "#f28e2b",
    "#e15759",
    "#76b7b2",
    "#59a14f",
    "#edc948",
    "#b07aa1",
    "#ff9da7",
    "#9c755f",
    "#bab0ac",
)


# treescape's pinned viridis approximation: 11 keystops, linearly
# interpolated. Visually faithful to matplotlib's viridis but not
# byte-identical — see docs/conventions.md (v0.3, continuous color).
VIRIDIS_LUT = (
    (68, 1, 84),
    (72, 36, 117),
    (64, 65, 132),
    (52, 91, 140),
    (42, 116, 142),
    (34, 139, 141),
    (30, 161, 133),
    (68, 185, 116),
    (135, 206, 69),
    (211, 226, 45),
    (253, 231, 37),
)


def viridis(t: float) -> tuple[int, int, int, int]:
    """Map ``t in [0, 1]`` to an RGBA color via the pinned LUT.

    ``round`` is Python's round-half-to-even; NaN raises ``ValueError``
    from ``int()`` exactly as v0.4 did.
    """
    if t <= 0.0:
        r, g, b = VIRIDIS_LUT[0]
        return (r, g, b, 255)
    if t >= 1.0:
        r, g, b = VIRIDIS_LUT[-1]
        return (r, g, b, 255)
    n = len(VIRIDIS_LUT) - 1
    pos = t * n
    lo = int(pos)
    frac = pos - lo
    r0, g0, b0 = VIRIDIS_LUT[lo]
    r1, g1, b1 = VIRIDIS_LUT[lo + 1]
    r = int(round(r0 + frac * (r1 - r0)))
    g = int(round(g0 + frac * (g1 - g0)))
    b = int(round(b0 + frac * (b1 - b0)))
    return (r, g, b, 255)


def default_palette(n_values: int) -> list[str]:
    """Tableau-10 in first-occurrence order; more than 10 values raise."""
    if n_values > len(TABLEAU_10):
        raise ValueError("default categorical palette supports at most 10 values")
    return list(TABLEAU_10[:n_values])


def neumaier_sum(values: Sequence[float]) -> float:
    """Float sum with CPython >= 3.12 builtin ``sum()`` semantics.

    v0.4 called builtin ``sum()``, whose float algorithm changed in 3.12.
    Spelled out here so the oracle does not depend on the interpreter.
    """
    total = 0.0
    comp = 0.0
    for x in values:
        t = total + x
        if abs(total) >= abs(x):
            comp += (total - t) + x
        else:
            comp += (x - t) + total
        total = t
    if comp and math.isfinite(comp):
        total += comp
    return total


def value_range(
    tip_values: Sequence[Optional[float]],
    vmin: Optional[float],
    vmax: Optional[float],
) -> tuple[float, float]:
    numeric = [v for v in tip_values if v is not None]
    lo = vmin if vmin is not None else (min(numeric) if numeric else 0.0)
    hi = vmax if vmax is not None else (max(numeric) if numeric else 1.0)
    return lo, hi


def normalize(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        # Degenerate range (all values equal, or pinned vmin>=vmax). Map to
        # the colormap midpoint — deterministic, unambiguous, no
        # divide-by-zero.
        return 0.5
    t = (value - lo) / (hi - lo)
    if t < 0.0:
        return 0.0
    if t > 1.0:
        return 1.0
    return t


def _tip_value_by_node(tree, tip_values: Sequence) -> dict:
    tips = [i for i in tree.preorder() if tree.is_tip(i)]
    if len(tips) != len(tip_values):
        raise ValueError(
            f"column has {len(tip_values)} value(s) but the tree has {len(tips)} tip(s)"
        )
    return dict(zip(tips, tip_values))


def descendant_tips(tree, node_id: int) -> list[int]:
    """Named descendant tips, left-to-right preorder (v0.4 ``_descendant_tips``)."""
    out = []
    stack = [node_id]
    while stack:
        current = stack.pop()
        if tree.is_tip(current):
            if tree.name(current):
                out.append(current)
        else:
            stack.extend(reversed(tree.children(current)))
    return out


def continuous_tip_t(
    tree, tip_values: Sequence[Optional[float]], lo: float, hi: float
) -> list[tuple[str, float]]:
    """``(tip_name, t)`` for every tip with a value, in tip order."""
    out = []
    for name, value in zip(tree.tip_order(), tip_values):
        if value is None:
            continue
        out.append((name, normalize(value, lo, hi)))
    return out


def _subtree_means(tree, tip_values: Sequence[Optional[float]]):
    by_node = _tip_value_by_node(tree, tip_values)
    root = tree.root
    for node_id in tree.preorder():
        if node_id == root:
            continue
        numeric = [by_node[t] for t in descendant_tips(tree, node_id) if by_node[t] is not None]
        if not numeric:
            continue  # no data → keep default, silent
        yield node_id, neumaier_sum(numeric) / len(numeric)


def continuous_branch_t(
    tree, tip_values: Sequence[Optional[float]], lo: float, hi: float
) -> list[tuple[int, float]]:
    """``(node_id, t)`` per branch from the subtree mean, preorder."""
    return [(n, normalize(m, lo, hi)) for n, m in _subtree_means(tree, tip_values)]


def branch_widths(
    tree,
    tip_values: Sequence[Optional[float]],
    lo: float,
    hi: float,
    wmin: float,
    wmax: float,
) -> list[tuple[int, float]]:
    """``(node_id, width)`` per branch from the subtree mean, preorder."""
    out = []
    for node_id, mean_value in _subtree_means(tree, tip_values):
        t = normalize(mean_value, lo, hi)
        out.append((node_id, wmin + t * (wmax - wmin)))
    return out


def discrete_branch_codes(
    tree, tip_codes: Sequence[Optional[int]]
) -> tuple[list[tuple[int, int]], list[int]]:
    """Monophyly rule over discrete codes.

    Returns ``(colored, non_monophyletic)``: ``(node_id, code)`` for
    branches whose named descendant tips all share one non-missing code,
    and the node ids (preorder) of branches with mixed or partial data.
    All-missing subtrees appear in neither list.
    """
    by_node = _tip_value_by_node(tree, tip_codes)
    root = tree.root
    colored = []
    non_mono = []
    for node_id in tree.preorder():
        if node_id == root:
            continue
        tips = descendant_tips(tree, node_id)
        observed = [by_node[t] for t in tips if by_node[t] is not None]
        distinct = []
        for code in observed:
            if code not in distinct:
                distinct.append(code)
        if len(distinct) == 1 and len(observed) == len(tips):
            colored.append((node_id, distinct[0]))
            continue
        if not observed:
            continue
        non_mono.append(node_id)
    return colored, non_mono
