"""Oracle runner for claim ``treescape-styling-determinism``.

Same input + same styling configuration → byte-identical SVG. This
extends ``treescape-svg-determinism`` (which covers rectangular and
circular geometric scenes) to the v0.2 Phase-3 styled-render path:
clade highlight rectangles and per-tip color overrides.

Three modes per fixture (matching the unstyled determinism test):

* **Repeated render parity** — render five times in the same process;
  assert all bytes equal. Catches HashMap iteration leakage in the
  styled path.
* **Snapshot golden** — checked-in styled SVGs at
  ``tests/fixtures/golden/<fixture>_styled.svg``. Regenerate via
  ``UPDATE_GOLDENS=1``.
* **Rust↔Python ref bytes** — Rust styled output (via the connector)
  must equal the Python reference styled output byte-for-byte for the
  same fixture and style spec.

Style spec used by these tests is fixture-specific but pinned in
``STYLE_SPECS`` below — keep it stable so the goldens stay valid.
"""

from __future__ import annotations

import json
import os
import pathlib
import time

import pytest

from treescape_reference.newick import parse as ref_parse
from treescape_reference.render import (
    CladeHighlight,
    SceneOptions,
    StyleSpec,
    build_rectangular_scene,
    render_svg,
)
from treescape_reference.scene import Color

try:
    from treescape_connector.py_tree import Tree as RustTree
    from treescape_connector.py_render import render_rectangular_styled_svg as rust_render

    HAVE_CONNECTOR = True
except ImportError:  # pragma: no cover
    HAVE_CONNECTOR = False


WORKSPACE = pathlib.Path(__file__).parent.parent.parent
FIXTURES_DIR = WORKSPACE / "tests" / "fixtures" / "trees"
GOLDEN_DIR = WORKSPACE / "tests" / "fixtures" / "golden"
REPORT_DIR = pathlib.Path(__file__).parent / "reports"


# Per-fixture style specs. Pinned to keep goldens stable.
# Each entry: (fixture_path, [(tip_names, color)], {tip_name: color}).
STYLE_SPECS = [
    (
        FIXTURES_DIR / "small" / "two_tip.nwk",
        [(["a"], (224, 123, 0, 76))],
        {"a": (255, 0, 0, 255)},
    ),
    (
        FIXTURES_DIR / "small" / "balanced_4.nwk",
        [
            (["a", "b"], (224, 123, 0, 76)),
            (["c", "d"], (0, 128, 255, 51)),
        ],
        {"a": (255, 0, 0, 255), "d": (0, 170, 0, 255)},
    ),
    (
        FIXTURES_DIR / "small" / "unbalanced_5.nwk",
        [
            (["a", "b", "c"], (192, 64, 192, 64)),
        ],
        {"e": (255, 128, 0, 255)},
    ),
    (
        FIXTURES_DIR / "edge" / "trifurcation_root.nwk",
        [(["a", "b"], (224, 123, 0, 76))],
        {"c": (0, 0, 255, 255)},
    ),
]


def _ref_render_styled(
    fixture: pathlib.Path,
    highlights: list,
    tip_colors: dict,
) -> str:
    """Render a styled scene through the Python reference path."""
    src = fixture.read_text()
    tree = ref_parse(src)
    style = StyleSpec(
        highlights=[
            CladeHighlight(tip_names=tuple(names), fill=Color(r, g, b, a))
            for names, (r, g, b, a) in highlights
        ],
        tip_colors={
            name: Color(r, g, b, a) for name, (r, g, b, a) in tip_colors.items()
        },
    )
    scene = build_rectangular_scene(tree, SceneOptions(), style=style)
    return render_svg(scene)


@pytest.mark.parametrize(
    "fixture,highlights,tip_colors",
    STYLE_SPECS,
    ids=[s[0].name for s in STYLE_SPECS],
)
def test_styled_render_repeated(
    fixture: pathlib.Path, highlights: list, tip_colors: dict
) -> None:
    """Five styled renders produce identical bytes (Python ref)."""
    first = _ref_render_styled(fixture, highlights, tip_colors)
    for _ in range(4):
        again = _ref_render_styled(fixture, highlights, tip_colors)
        assert again == first, f"styled render drift on {fixture.name}"


@pytest.mark.parametrize(
    "fixture,highlights,tip_colors",
    STYLE_SPECS,
    ids=[s[0].name for s in STYLE_SPECS],
)
def test_styled_matches_golden(
    fixture: pathlib.Path, highlights: list, tip_colors: dict
) -> None:
    """Styled render matches the checked-in golden."""
    rendered = _ref_render_styled(fixture, highlights, tip_colors)
    golden = GOLDEN_DIR / f"{fixture.stem}_styled.svg"
    if os.environ.get("UPDATE_GOLDENS") == "1":
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        golden.write_text(rendered)
        pytest.skip(f"updated golden {golden.name}")
    if not golden.exists():
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        golden.write_text(rendered)
        pytest.fail(
            f"styled golden {golden.name} did not exist; created it. Re-run."
        )
    expected = golden.read_text()
    assert rendered == expected, (
        f"styled golden mismatch on {fixture.name}; "
        f"set UPDATE_GOLDENS=1 to regenerate if intentional"
    )


@pytest.mark.skipif(
    not HAVE_CONNECTOR,
    reason="treescape_connector not built (run maturin develop)",
)
@pytest.mark.parametrize(
    "fixture,highlights,tip_colors",
    STYLE_SPECS,
    ids=[s[0].name for s in STYLE_SPECS],
)
def test_rust_styled_matches_python_reference_bytes(
    fixture: pathlib.Path, highlights: list, tip_colors: dict
) -> None:
    """Rust styled SVG byte-identical to Python reference styled SVG."""
    src = fixture.read_text()
    rust_svg = rust_render(
        RustTree.parse_newick(src),
        None,
        list(highlights),
        dict(tip_colors),
    )
    ref_svg = _ref_render_styled(fixture, highlights, tip_colors)
    assert rust_svg == ref_svg, (
        f"Rust/ref styled SVG diverged on {fixture.name}: "
        f"rust_len={len(rust_svg)} ref_len={len(ref_svg)}"
    )


@pytest.fixture(scope="session", autouse=True)
def _emit_report() -> None:
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-styling-determinism",
        "version": "0.1",
        "timestamp_utc": int(time.time()),
        "fixtures": [s[0].name for s in STYLE_SPECS],
        "modes": ["repeated_render", "golden_snapshot", "rust_vs_ref_bytes"],
        "tier": "ci",
    }
    (REPORT_DIR / "styling_determinism.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
