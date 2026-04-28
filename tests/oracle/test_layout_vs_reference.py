"""Oracle runner for claim ``treescape-layout-rust-vs-reference``.

Compares the Rust rectangular layout (via ``treescape_connector``)
against the Python reference (``treescape_reference``). Tolerance:
1e-9 absolute on (x, y) per node.

The Python reference is the canonical convention owner. This claim is
the proof that the Rust port has not drifted from the conventions
ete3, Biopython.Phylo, and ggtree are validated against in claims #3
through #5.
"""

from __future__ import annotations

import json
import pathlib
import time

import pytest

from treescape_reference.layout import (
    circular_layout as ref_circular_layout,
    rectangular_layout as ref_layout,
    tips_by_name,
)
from treescape_reference.newick import parse as ref_parse

try:
    from treescape_connector.py_tree import Tree as RustTree
    from treescape_connector.py_layout import (
        circular_layout as rust_circular_layout,
        rectangular_layout as rust_layout,
    )

    HAVE_CONNECTOR = True
except ImportError:  # pragma: no cover - only true before maturin develop
    HAVE_CONNECTOR = False


FIXTURES_DIR = pathlib.Path(__file__).parent.parent / "fixtures" / "trees"
REPORT_DIR = pathlib.Path(__file__).parent / "reports"

PARITY_FIXTURES = [
    FIXTURES_DIR / "small" / "two_tip.nwk",
    FIXTURES_DIR / "small" / "balanced_4.nwk",
    FIXTURES_DIR / "small" / "unbalanced_5.nwk",
    FIXTURES_DIR / "edge" / "trifurcation_root.nwk",
]

TOL = 1e-9


@pytest.mark.skipif(
    not HAVE_CONNECTOR,
    reason="treescape_connector not built (run maturin develop)",
)
@pytest.mark.parametrize("fixture", PARITY_FIXTURES, ids=lambda p: p.name)
def test_rust_layout_matches_reference(fixture: pathlib.Path) -> None:
    src = fixture.read_text()

    rust_tree = RustTree.parse_newick(src)
    rust_l = rust_layout(rust_tree)
    rust_tips = {name: (x, y) for name, x, y in rust_l.tips_by_name(rust_tree)}

    ref_tree = ref_parse(src)
    ref_coords = ref_layout(ref_tree)
    ref_tips = tips_by_name(ref_tree, ref_coords)

    assert set(rust_tips) == set(ref_tips), (
        f"tip name set differs on {fixture.name}: "
        f"rust={set(rust_tips)} ref={set(ref_tips)}"
    )
    for name in rust_tips:
        rx, ry = rust_tips[name]
        ex, ey = ref_tips[name]
        assert abs(rx - ex) < TOL, (
            f"x drift on {fixture.name}/{name}: rust={rx} ref={ex} delta={rx-ex}"
        )
        assert abs(ry - ey) < TOL, (
            f"y drift on {fixture.name}/{name}: rust={ry} ref={ey} delta={ry-ey}"
        )


@pytest.mark.skipif(
    not HAVE_CONNECTOR,
    reason="treescape_connector not built (run maturin develop)",
)
@pytest.mark.parametrize("fixture", PARITY_FIXTURES, ids=lambda p: p.name)
def test_rust_circular_layout_matches_reference(fixture: pathlib.Path) -> None:
    """Phase 2 extension of the rust-vs-reference parity claim:
    circular ``(r, θ)`` per tip must match the Python reference within
    1e-9. Convention owner is the Python reference; Rust port is held
    to it. See ``docs/conventions.md`` for the circular convention."""
    src = fixture.read_text()

    rust_tree = RustTree.parse_newick(src)
    rust_l = rust_circular_layout(rust_tree)
    rust_tips = {name: (r, t) for name, r, t in rust_l.tips_by_name(rust_tree)}

    ref_tree = ref_parse(src)
    ref_coords = ref_circular_layout(ref_tree)
    ref_tips = tips_by_name(ref_tree, ref_coords)

    assert set(rust_tips) == set(ref_tips), (
        f"tip name set differs on {fixture.name}: "
        f"rust={set(rust_tips)} ref={set(ref_tips)}"
    )
    for name in rust_tips:
        rr, rt = rust_tips[name]
        er, et = ref_tips[name]
        assert abs(rr - er) < TOL, (
            f"r drift on {fixture.name}/{name}: rust={rr} ref={er} delta={rr-er}"
        )
        assert abs(rt - et) < TOL, (
            f"θ drift on {fixture.name}/{name}: rust={rt} ref={et} delta={rt-et}"
        )


@pytest.fixture(scope="session", autouse=True)
def _emit_report() -> None:
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-layout-rust-vs-reference",
        "version": "0.1",
        "timestamp_utc": int(time.time()),
        "fixtures": [f.name for f in PARITY_FIXTURES],
        "tolerance": TOL,
        "connector_available": HAVE_CONNECTOR,
    }
    (REPORT_DIR / "layout_rust_vs_reference.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
