"""Oracle runner for claim ``treescape-svg-determinism``.

The Python reference renderer must produce byte-identical SVG bytes
across runs for fixed input + fixed options. We assert this in two
ways:

* **Repeated render parity** — render a fixture five times in the same
  process; assert all bytes equal. Catches HashMap iteration order
  leakage and other in-process non-determinism.

* **Snapshot golden** — for each fixture we keep a checked-in golden
  SVG in ``tests/fixtures/golden/<fixture>.svg``. The current render
  must match the golden byte-for-byte. Goldens are regenerated only
  via ``UPDATE_GOLDENS=1 pytest tests/oracle/test_svg_determinism.py``.

The Rust path is verified by ``cargo test svg::tests::render_is_byte_deterministic``
(treescape-render). End-to-end Rust↔Python byte equality is part of
Phase 4 once the connector is wired.
"""

from __future__ import annotations

import json
import os
import pathlib
import time

import pytest

from treescape_reference.newick import parse as ref_parse
from treescape_reference.render import (
    SceneOptions,
    build_circular_scene,
    build_rectangular_scene,
    render_svg,
)

try:
    from treescape_connector.py_tree import Tree as RustTree
    from treescape_connector.py_render import (
        render_circular_svg as rust_render_circular,
        render_rectangular_svg as rust_render,
    )

    HAVE_CONNECTOR = True
except ImportError:  # pragma: no cover - only before maturin develop
    HAVE_CONNECTOR = False


WORKSPACE = pathlib.Path(__file__).parent.parent.parent
FIXTURES_DIR = WORKSPACE / "tests" / "fixtures" / "trees"
GOLDEN_DIR = WORKSPACE / "tests" / "fixtures" / "golden"
REPORT_DIR = pathlib.Path(__file__).parent / "reports"

DETERMINISM_FIXTURES = [
    FIXTURES_DIR / "small" / "two_tip.nwk",
    FIXTURES_DIR / "small" / "balanced_4.nwk",
    FIXTURES_DIR / "small" / "unbalanced_5.nwk",
    FIXTURES_DIR / "edge" / "trifurcation_root.nwk",
]


def _render(fixture: pathlib.Path) -> str:
    src = fixture.read_text()
    tree = ref_parse(src)
    scene = build_rectangular_scene(tree, SceneOptions())
    return render_svg(scene)


@pytest.mark.parametrize("fixture", DETERMINISM_FIXTURES, ids=lambda p: p.name)
def test_repeated_render_byte_identical(fixture: pathlib.Path) -> None:
    """Five renders of the same fixture produce identical bytes."""
    first = _render(fixture)
    for _ in range(4):
        again = _render(fixture)
        assert again == first, f"render drift on {fixture.name}"


@pytest.mark.parametrize("fixture", DETERMINISM_FIXTURES, ids=lambda p: p.name)
def test_matches_golden(fixture: pathlib.Path) -> None:
    """Current render bytes match the checked-in golden."""
    rendered = _render(fixture)
    golden = GOLDEN_DIR / f"{fixture.stem}.svg"
    if os.environ.get("UPDATE_GOLDENS") == "1":
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        golden.write_text(rendered)
        pytest.skip(f"updated golden {golden.name}")
    if not golden.exists():
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        golden.write_text(rendered)
        pytest.fail(
            f"golden {golden.name} did not exist; created it. Re-run to validate."
        )
    expected = golden.read_text()
    assert rendered == expected, (
        f"golden mismatch on {fixture.name}; "
        f"set UPDATE_GOLDENS=1 to regenerate if intentional"
    )


@pytest.mark.skipif(
    not HAVE_CONNECTOR,
    reason="treescape_connector not built (run maturin develop)",
)
@pytest.mark.parametrize("fixture", DETERMINISM_FIXTURES, ids=lambda p: p.name)
def test_rust_matches_python_reference_bytes(fixture: pathlib.Path) -> None:
    """Rust SVG output is byte-identical to the Python reference output.

    The Python reference renderer was deliberately written to produce
    the exact same byte stream as the Rust impl for the v0.1 default
    options. This test enforces that contract directly — drift in
    either path lights up here.
    """
    src = fixture.read_text()
    rust_svg = rust_render(RustTree.parse_newick(src))
    ref_svg = render_svg(build_rectangular_scene(ref_parse(src), SceneOptions()))
    assert rust_svg == ref_svg, (
        f"Rust/reference SVG bytes diverged on {fixture.name}: "
        f"rust_len={len(rust_svg)} ref_len={len(ref_svg)}"
    )


def _render_circular(fixture: pathlib.Path) -> str:
    src = fixture.read_text()
    tree = ref_parse(src)
    scene = build_circular_scene(tree, SceneOptions())
    return render_svg(scene)


@pytest.mark.parametrize("fixture", DETERMINISM_FIXTURES, ids=lambda p: p.name)
def test_circular_repeated_render_byte_identical(fixture: pathlib.Path) -> None:
    """Five circular renders produce identical bytes (Python ref)."""
    first = _render_circular(fixture)
    for _ in range(4):
        assert _render_circular(fixture) == first, f"circular render drift on {fixture.name}"


@pytest.mark.parametrize("fixture", DETERMINISM_FIXTURES, ids=lambda p: p.name)
def test_circular_matches_golden(fixture: pathlib.Path) -> None:
    """Current circular render bytes match checked-in golden."""
    rendered = _render_circular(fixture)
    golden = GOLDEN_DIR / f"{fixture.stem}_circular.svg"
    if os.environ.get("UPDATE_GOLDENS") == "1":
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        golden.write_text(rendered)
        pytest.skip(f"updated golden {golden.name}")
    if not golden.exists():
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        golden.write_text(rendered)
        pytest.fail(
            f"golden {golden.name} did not exist; created it. Re-run to validate."
        )
    expected = golden.read_text()
    assert rendered == expected, (
        f"circular golden mismatch on {fixture.name}; "
        f"set UPDATE_GOLDENS=1 to regenerate if intentional"
    )


@pytest.mark.skipif(
    not HAVE_CONNECTOR,
    reason="treescape_connector not built (run maturin develop)",
)
@pytest.mark.parametrize("fixture", DETERMINISM_FIXTURES, ids=lambda p: p.name)
def test_rust_circular_matches_python_reference_bytes(fixture: pathlib.Path) -> None:
    """Rust circular SVG byte-identical to Python reference."""
    src = fixture.read_text()
    rust_svg = rust_render_circular(RustTree.parse_newick(src))
    ref_svg = render_svg(build_circular_scene(ref_parse(src), SceneOptions()))
    assert rust_svg == ref_svg, (
        f"Rust/ref circular SVG diverged on {fixture.name}: "
        f"rust_len={len(rust_svg)} ref_len={len(ref_svg)}"
    )


@pytest.fixture(scope="session", autouse=True)
def _emit_report() -> None:
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-svg-determinism",
        "version": "0.1",
        "timestamp_utc": int(time.time()),
        "fixtures": [f.name for f in DETERMINISM_FIXTURES],
        "modes": ["repeated_render", "golden_snapshot"],
    }
    (REPORT_DIR / "svg_determinism.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
