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

from treescape_reference.layout import circular_layout, clade_tips, find_mrca
from treescape_reference.newick import parse as ref_parse
from treescape_reference.render import (
    CladeHighlight,
    SceneOptions,
    StyleSpec,
    build_circular_scene,
    build_rectangular_scene,
    render_svg,
)
from treescape_reference.scene import AnnularSector, Color

try:
    from treescape_connector.py_tree import Tree as RustTree
    from treescape_connector.py_render import (
        CircularSceneOptions as RustCircularSceneOptions,
        render_circular_styled_svg as rust_render_circular,
        render_rectangular_styled_svg as rust_render,
    )

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


# v0.3 Phase 3: circular highlight cases. Single-tip highlights make
# zero-angular-extent sectors (degenerate); whole-tree highlights raise
# (MRCA == root). So circular fixtures use ≥2-tip non-root clades.
CIRCULAR_STYLE_SPECS = [
    (
        FIXTURES_DIR / "small" / "balanced_4.nwk",
        [
            (["a", "b"], (224, 123, 0, 76)),
            (["c", "d"], (0, 128, 255, 51)),
        ],
    ),
    (
        FIXTURES_DIR / "small" / "unbalanced_5.nwk",
        [
            (["a", "b"], (224, 123, 0, 76)),
            (["a", "b", "c"], (192, 64, 192, 64)),
        ],
    ),
]


def _ref_render_circular_styled(fixture: pathlib.Path, highlights: list) -> str:
    """Render a circular styled scene through the Python reference."""
    src = fixture.read_text()
    tree = ref_parse(src)
    style = StyleSpec(
        highlights=[
            CladeHighlight(tip_names=tuple(names), fill=Color(r, g, b, a))
            for names, (r, g, b, a) in highlights
        ],
    )
    scene = build_circular_scene(tree, SceneOptions(), style=style)
    return render_svg(scene)


@pytest.mark.parametrize(
    "fixture,highlights",
    CIRCULAR_STYLE_SPECS,
    ids=[s[0].name for s in CIRCULAR_STYLE_SPECS],
)
def test_circular_styled_render_repeated(
    fixture: pathlib.Path, highlights: list
) -> None:
    """Five circular styled renders produce identical bytes (Python ref)."""
    first = _ref_render_circular_styled(fixture, highlights)
    for _ in range(4):
        again = _ref_render_circular_styled(fixture, highlights)
        assert again == first, f"circular styled drift on {fixture.name}"


@pytest.mark.parametrize(
    "fixture,highlights",
    CIRCULAR_STYLE_SPECS,
    ids=[s[0].name for s in CIRCULAR_STYLE_SPECS],
)
def test_circular_styled_matches_golden(
    fixture: pathlib.Path, highlights: list
) -> None:
    """Circular styled render matches the checked-in golden."""
    rendered = _ref_render_circular_styled(fixture, highlights)
    golden = GOLDEN_DIR / f"{fixture.stem}_styled_circular.svg"
    if os.environ.get("UPDATE_GOLDENS") == "1":
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        golden.write_text(rendered)
        pytest.skip(f"updated golden {golden.name}")
    if not golden.exists():
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        golden.write_text(rendered)
        pytest.fail(
            f"circular styled golden {golden.name} did not exist; created it. Re-run."
        )
    expected = golden.read_text()
    assert rendered == expected, (
        f"circular styled golden mismatch on {fixture.name}; "
        f"set UPDATE_GOLDENS=1 to regenerate if intentional"
    )


@pytest.mark.skipif(
    not HAVE_CONNECTOR,
    reason="treescape_connector not built (run pip install -e ./treescape-connector)",
)
@pytest.mark.parametrize(
    "fixture,highlights",
    CIRCULAR_STYLE_SPECS,
    ids=[s[0].name for s in CIRCULAR_STYLE_SPECS],
)
def test_rust_circular_styled_matches_python_reference_bytes(
    fixture: pathlib.Path, highlights: list
) -> None:
    """Rust circular styled SVG byte-identical to Python reference."""
    src = fixture.read_text()
    rust_svg = rust_render_circular(
        RustTree.parse_newick(src),
        None,
        list(highlights),
    )
    ref_svg = _ref_render_circular_styled(fixture, highlights)
    assert rust_svg == ref_svg, (
        f"Rust/ref circular styled SVG diverged on {fixture.name}: "
        f"rust_len={len(rust_svg)} ref_len={len(ref_svg)}"
    )


def test_circular_highlight_mrca_is_root_raises() -> None:
    """Whole-tree highlight on circular layout raises ValueError per
    docs/conventions.md (v0.3 Phase 3). Tested at the Python ref layer
    and the Rust connector layer (which converts the Result::Err to
    PyValueError)."""
    src = (FIXTURES_DIR / "small" / "balanced_4.nwk").read_text()
    style = StyleSpec(
        highlights=[
            CladeHighlight(tip_names=("a", "b", "c", "d"), fill=Color(255, 0, 0, 76))
        ]
    )
    with pytest.raises(ValueError, match="MRCA == root"):
        build_circular_scene(ref_parse(src), SceneOptions(), style=style)

    if HAVE_CONNECTOR:
        with pytest.raises(ValueError, match="MRCA == root"):
            rust_render_circular(
                RustTree.parse_newick(src),
                None,
                [(["a", "b", "c", "d"], (255, 0, 0, 76))],
            )


def test_circular_annular_sector_angular_bounds_equal_clade_tip_angles() -> None:
    """Property: an annular sector's [theta_min, theta_max] equals the
    min/max layout tip angles in the clade (the polar analogue of the
    rectangular "row span equals clade tip rows" property). The radial
    bounds use the layout's own r_max + label_zone outer radius — no
    rectangular↔circular shape equivalence claimed under the polar
    transform."""
    src = (FIXTURES_DIR / "small" / "balanced_4.nwk").read_text()
    tree = ref_parse(src)
    coords = circular_layout(tree)
    style = StyleSpec(
        highlights=[
            CladeHighlight(tip_names=("a", "b"), fill=Color(255, 0, 0, 76)),
        ]
    )
    scene = build_circular_scene(tree, SceneOptions(), style=style)
    sectors = [item for item in scene.items if isinstance(item, AnnularSector)]
    assert len(sectors) == 1, f"expected 1 sector, got {len(sectors)}"
    sec = sectors[0]

    mrca = find_mrca(tree, ["a", "b"])
    clade = clade_tips(tree, mrca)
    tip_thetas = [coords[id(n)][1] for n in clade]
    expected_min = min(tip_thetas)
    expected_max = max(tip_thetas)

    assert abs(sec.theta_min - expected_min) < 1e-12
    assert abs(sec.theta_max - expected_max) < 1e-12


@pytest.fixture(scope="session", autouse=True)
def _emit_report() -> None:
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-styling-determinism",
        "version": "0.3",
        "timestamp_utc": int(time.time()),
        "rectangular_fixtures": [s[0].name for s in STYLE_SPECS],
        "circular_fixtures": [s[0].name for s in CIRCULAR_STYLE_SPECS],
        "modes": [
            "repeated_render",
            "golden_snapshot",
            "rust_vs_ref_bytes",
            "circular_mrca_root_raises",
            "circular_angular_bounds_property",
        ],
        "tier": "ci",
    }
    (REPORT_DIR / "styling_determinism.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
