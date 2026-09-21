"""Oracle runner for claim ``treescape-style-resolution-rust-vs-reference``.

The Rust resolver (``treescape_connector.py_style`` → ``treescape-core``
``style.rs``) must return exactly what ``treescape_reference.style``
returns: identical integers, bit-identical non-NaN floats, NaN compared
by classification ("both NaN" — not sign or payload bits), and identical
exception type + message for out-of-domain input.

Coverage: pinned fixtures for each byte-parity trap in
docs/conventions.md (v0.5 Phase 1) — Neumaier-sensitive subtree sums,
exact ``.5`` viridis channels, degenerate ranges, NaN, unnamed tips —
plus hypothesis-generated trees and columns.
"""

from __future__ import annotations

import json
import math
import random
import struct
import sys
import time
from pathlib import Path

import pytest

hypothesis = pytest.importorskip(
    "hypothesis",
    reason="hypothesis not installed (declared in packages/treescape-reference[test])",
)
from hypothesis import HealthCheck, given, settings, strategies as st  # noqa: E402

rust = pytest.importorskip(
    "treescape_connector.py_style",
    reason="treescape_connector not built (run pip install -e ./treescape-connector)",
)
from treescape_connector.py_tree import Tree  # noqa: E402
from treescape_reference import style as ref  # noqa: E402


REPORT_DIR = Path(__file__).parent / "reports"
_COUNTS: dict[str, int] = {}


def _count(name: str) -> None:
    _COUNTS[name] = _COUNTS.get(name, 0) + 1


def _canon(x):
    """Exact-comparison form: floats → bit pattern (NaN → marker)."""
    if isinstance(x, float):
        return "nan" if math.isnan(x) else struct.pack("<d", x)
    if isinstance(x, (list, tuple)):
        return [_canon(v) for v in x]
    return x


def assert_exact(a, b) -> None:
    assert _canon(a) == _canon(b), f"{a!r} != {b!r}"


def _both(fn_name: str, *args):
    """Call the same function on both sides; errors must match too."""
    outcomes = []
    for impl in (ref, rust):
        try:
            outcomes.append(("ok", getattr(impl, fn_name)(*args)))
        except Exception as exc:  # noqa: BLE001 - the error itself is compared
            outcomes.append((type(exc).__name__, str(exc)))
    (ref_kind, ref_val), (rust_kind, rust_val) = outcomes
    assert ref_kind == rust_kind, f"{fn_name}: reference {ref_kind} {ref_val!r}, rust {rust_kind} {rust_val!r}"
    if ref_kind == "ok":
        assert_exact(ref_val, rust_val)
    else:
        assert ref_val == rust_val
    _count(fn_name)
    return ref_val


# ---------------------------------------------------------------------------
# Constants and scalar functions
# ---------------------------------------------------------------------------


def test_pinned_constants_match():
    assert list(rust.TABLEAU_10) == list(ref.TABLEAU_10)
    assert [tuple(c) for c in rust.VIRIDIS_LUT] == list(ref.VIRIDIS_LUT)


@pytest.mark.parametrize("n", range(0, 13))
def test_default_palette(n):
    _both("default_palette", n)


def test_viridis_grid_and_specials():
    ts = [k / 10_000 for k in range(-100, 10_101)]
    ts += [-0.0, math.inf, -math.inf, 5e-324, 1 - 2**-53, math.nan]
    for t in ts:
        _both("viridis", t)


def test_viridis_hits_exact_half_channels():
    """Round-half-to-even is only exercised where a channel lands on x.5
    exactly. Find such t values and check both sides on them."""
    halves = []
    for k in range(1, 100_000):
        t = k / 100_000
        pos = t * (len(ref.VIRIDIS_LUT) - 1)
        lo = int(pos)
        frac = pos - lo
        for c in range(3):
            c0, c1 = ref.VIRIDIS_LUT[lo][c], ref.VIRIDIS_LUT[lo + 1][c]
            v = c0 + frac * (c1 - c0)
            if v % 1 == 0.5:
                halves.append((t, v))
    assert halves, "no exact .5 channel found; widen the scan"
    # At least one tie must round down to even, or the trap is not covered.
    assert any(int(v) % 2 == 0 for _, v in halves)
    for t, _ in halves:
        _both("viridis", t)


_float = st.floats(allow_nan=True, allow_infinity=True)


@settings(max_examples=500, deadline=None)
@given(st.lists(_float, max_size=40))
def test_neumaier_sum(values):
    _both("neumaier_sum", values)


def test_neumaier_sensitive_fixtures():
    for values in ([1e16, 1.0, -1e16], [0.1] * 10, [1e308, 1e308, -1e308], [-0.0], []):
        _both("neumaier_sum", values)


@pytest.mark.skipif(sys.version_info < (3, 12), reason="builtin sum() is Neumaier only on 3.12+")
@settings(max_examples=500, deadline=None)
@given(st.lists(st.floats(allow_nan=False, allow_infinity=False), max_size=40))
def test_reference_sum_is_builtin_sum_on_312(values):
    """Ties the pinned algorithm to what v0.4 goldens were generated with."""
    assert_exact(ref.neumaier_sum(values), float(sum(values)))


@settings(max_examples=500, deadline=None)
@given(
    st.lists(st.one_of(st.none(), _float), max_size=20),
    st.one_of(st.none(), _float),
    st.one_of(st.none(), _float),
)
def test_value_range(values, vmin, vmax):
    _both("value_range", values, vmin, vmax)


@settings(max_examples=1000, deadline=None)
@given(_float, _float, _float)
def test_normalize(value, lo, hi):
    _both("normalize", value, lo, hi)


# ---------------------------------------------------------------------------
# Tree-level resolution
# ---------------------------------------------------------------------------


def _random_newick(rng: random.Random, n_tips: int, unnamed_rate: float) -> str:
    """Multifurcating random tree; some tips unnamed."""
    nodes = []
    for i in range(n_tips):
        name = "" if rng.random() < unnamed_rate else f"t{i}"
        nodes.append(f"{name}:{rng.uniform(0.0, 2.0):.3f}")
    while len(nodes) > 1:
        k = min(len(nodes), rng.choice([2, 2, 2, 3, 4]))
        group = [nodes.pop(rng.randrange(len(nodes))) for _ in range(k)]
        nodes.append(f"({','.join(group)}):{rng.uniform(0.0, 2.0):.3f}")
    root = nodes[0]
    if root.startswith("("):
        root = root[: root.rindex(")") + 1]
    return root + ";"


_value = st.one_of(
    st.none(),
    st.floats(min_value=-1e6, max_value=1e6),
    st.sampled_from([1e16, -1e16, 0.1, 1.0, 0.5, -0.0]),
)


def _check_tree(tree: Tree, values, codes, vmin, vmax, wmin, wmax) -> None:
    lo, hi = _both("value_range", values, vmin, vmax)
    _both("continuous_tip_t", tree, values, lo, hi)
    _both("continuous_branch_t", tree, values, lo, hi)
    _both("branch_widths", tree, values, lo, hi, wmin, wmax)
    _both("discrete_branch_codes", tree, codes)
    for node in tree.preorder():
        _both("descendant_tips", tree, node)


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    seed=st.integers(0, 2**32 - 1),
    n_tips=st.integers(1, 40),
    unnamed_rate=st.sampled_from([0.0, 0.0, 0.2]),
    data=st.data(),
)
def test_tree_resolution_random(seed, n_tips, unnamed_rate, data):
    tree = Tree.parse_newick(_random_newick(random.Random(seed), n_tips, unnamed_rate))
    n = len(tree.tip_order())
    values = data.draw(st.lists(_value, min_size=n, max_size=n))
    codes = data.draw(st.lists(st.one_of(st.none(), st.integers(0, 3)), min_size=n, max_size=n))
    vmin = data.draw(st.one_of(st.none(), st.floats(-10, 10)))
    vmax = data.draw(st.one_of(st.none(), st.floats(-10, 10)))
    _check_tree(tree, values, codes, vmin, vmax, 1.0, 4.0)


FIXTURES = {
    # Neumaier-sensitive clade: plain summation gives mean 0.0, Neumaier 1/3.
    "neumaier_clade": ("((a:1,b:1,c:1):1,d:1);", [1e16, 1.0, -1e16, 2.0]),
    "degenerate_range": ("((a:1,b:1):1,(c:1,d:1):1);", [0.7, 0.7, 0.7, 0.7]),
    "nan_value": ("((a:1,b:1):1,(c:1,d:1):1);", [math.nan, 0.2, 0.3, 0.4]),
    "unnamed_tips": ("((a:1,:1):1,(:1,d:1):1);", [0.1, 0.9, 0.5, None]),
    "all_missing": ("((a:1,b:1):1,c:1);", [None, None, None]),
    "single_tip": ("a;", [0.3]),
}


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_tree_resolution_fixtures(name):
    newick, values = FIXTURES[name]
    tree = Tree.parse_newick(newick)
    codes = [None if v is None or math.isnan(v) else int(abs(v) * 10) % 3 for v in values]
    _check_tree(tree, values, codes, None, None, 1.0, 4.0)
    _check_tree(tree, values, codes, 0.0, 1.0, 0.5, 6.0)


def test_neumaier_clade_actually_differs_from_naive():
    """Guard: the fixture must be one where the algorithm choice matters."""
    tree = Tree.parse_newick(FIXTURES["neumaier_clade"][0])
    values = FIXTURES["neumaier_clade"][1]
    clade = [n for n, _ in rust.continuous_branch_t(tree, values, 0.0, 1.0)][0]
    naive = (1e16 + 1.0 + -1e16) / 3
    means = dict(ref._subtree_means(tree, values))
    assert naive == 0.0 and means[clade] == pytest.approx(1 / 3)


@pytest.mark.parametrize("length", [0, 1, 2, 4, 7])
def test_column_length_mismatch_errors_match(length):
    """Every column-taking function rejects short, empty, and overlong
    columns identically (the tree has 3 tips)."""
    tree = Tree.parse_newick("((a:1,b:1):1,c:1);")
    values = [0.1] * length
    codes = [0] * length
    _both("continuous_tip_t", tree, values, 0.0, 1.0)
    _both("continuous_branch_t", tree, values, 0.0, 1.0)
    _both("branch_widths", tree, values, 0.0, 1.0, 1.0, 4.0)
    _both("discrete_branch_codes", tree, codes)


@pytest.mark.parametrize("n", [-1, 10, 11, 2**63 - 1, 2**63, 2**100, -(2**100), True, 3.0, "3", None])
def test_default_palette_domain(n):
    _both("default_palette", n)


@pytest.mark.parametrize(
    "codes",
    [
        [0, 2**32 - 1, None],
        [2**32, 0, None],
        [-1, 0, None],
        [2**100, 0, None],
        [True, False, None],
        [1.0, 0, None],
        ["a", 0, None],
    ],
)
def test_discrete_code_domain(codes):
    tree = Tree.parse_newick("((a:1,b:1):1,c:1);")
    _both("discrete_branch_codes", tree, codes)


@pytest.mark.parametrize("node", [0, 4, 5, -1, 2**63, 2**100, True, 1.0, "0", None])
def test_node_id_domain(node):
    tree = Tree.parse_newick("((a:1,b:1):1,c:1);")  # 5 nodes
    _both("descendant_tips", tree, node)


def test_neumaier_mean_through_treeplot_on_every_interpreter():
    """v0.4 used builtin sum(): this width was 1.0 on Python 3.11 and 2.0
    on 3.12. v0.5 pins 2.0 everywhere (docs/conventions.md, v0.5 Phase 1)."""
    pl = pytest.importorskip("polars", reason="polars required for TreePlot metadata")
    from treescape import TreePlot

    newick, values = FIXTURES["neumaier_clade"]
    plot = TreePlot(newick).join_metadata(
        pl.DataFrame({"tip": ["a", "b", "c", "d"], "v": values}), on="tip"
    )
    plot.width_branches_by("v", vmin=0.0, vmax=1.0)
    tree = plot._tree
    clade = next(n for n in tree.preorder() if n != tree.root and not tree.is_tip(n))  # (a,b,c)
    assert plot._branch_widths[clade] == 2.0


@pytest.fixture(scope="session", autouse=True)
def _emit_report() -> None:
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-style-resolution-rust-vs-reference",
        "version": "0.5",
        "timestamp_utc": int(time.time()),
        "tier": "ci",
        "tolerance": "exact (f64 bit patterns; NaN compared as NaN)",
        "python": sys.version.split()[0],
        "comparisons_by_function": dict(sorted(_COUNTS.items())),
    }
    (REPORT_DIR / "style_resolution.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
