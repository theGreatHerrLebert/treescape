"""Oracle runner for claim ``treescape-circular-annotation-determinism``.

Property: same tree + same scene options + same ``(scale_bar,
support_labels)`` configuration → byte-identical SVG on the circular
path. Convention assertions are part of the claim:

* scale-bar ``bar_x2`` equals ``canvas_width - padding`` (bar in the
  bottom-right corner, extending leftward from the right edge);
* support-label ``rotation_deg == 0`` (upright) and
  ``anchor == Middle`` (centered on the projected node position);
* Rust↔Python ref byte parity holds because both impls share the
  locked convention.

v0.4 Phase 2.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import time

import pytest

from treescape_reference.newick import parse as ref_parse
from treescape_reference.render import (
    SceneOptions,
    ScaleBar,
    StyleSpec,
    SupportLabelSpec,
    build_circular_scene,
    render_svg,
)

try:
    from treescape_connector.py_render import (
        render_circular_styled_svg as rust_render_circular,
    )
    from treescape_connector.py_tree import Tree as RustTree

    HAVE_CONNECTOR = True
except ImportError:  # pragma: no cover
    HAVE_CONNECTOR = False


WORKSPACE = pathlib.Path(__file__).parent.parent.parent
FIXTURES_DIR = WORKSPACE / "tests" / "fixtures" / "trees"
GOLDEN_DIR = WORKSPACE / "tests" / "fixtures" / "golden"
REPORT_DIR = pathlib.Path(__file__).parent / "reports"


# Pinned circular annotation configurations. Each entry:
# (fixture_path, scale_bar_or_None, support_min_or_None, support_enabled).
ANNOTATION_SPECS = [
    (
        FIXTURES_DIR / "small" / "balanced_4.nwk",
        ScaleBar(length=0.5, label="0.5 subs/site"),
        None,
        False,
    ),
    (
        FIXTURES_DIR / "small" / "unbalanced_5.nwk",
        ScaleBar(length=1.0, label="1 unit"),
        None,
        False,
    ),
]


# Trees with internal-node names — required for support_labels to have anything to render.
SUPPORT_LABEL_NEWICKS = [
    ("two_internal", "((a:1,b:1)inner:1,(c:1,d:1)other:1);", None),
    ("with_filter", "((a:1,b:1)95:1,(c:1,d:1)50:1);", 70.0),
]


def _ref_render_annotated(
    fixture: pathlib.Path,
    scale_bar: ScaleBar | None,
    support_min: float | None,
    support_enabled: bool,
) -> str:
    src = fixture.read_text()
    tree = ref_parse(src)
    style = StyleSpec(
        scale_bar=scale_bar,
        support_labels=(
            SupportLabelSpec(min_value=support_min) if support_enabled else None
        ),
    )
    return render_svg(build_circular_scene(tree, SceneOptions(), style=style))


def _ref_render_from_newick(
    newick: str,
    scale_bar: ScaleBar | None,
    support_min: float | None,
    support_enabled: bool,
) -> str:
    tree = ref_parse(newick)
    style = StyleSpec(
        scale_bar=scale_bar,
        support_labels=(
            SupportLabelSpec(min_value=support_min) if support_enabled else None
        ),
    )
    return render_svg(build_circular_scene(tree, SceneOptions(), style=style))


@pytest.mark.parametrize(
    "fixture,scale_bar,support_min,support_enabled",
    ANNOTATION_SPECS,
    ids=[s[0].name for s in ANNOTATION_SPECS],
)
def test_circular_annotation_render_repeated(
    fixture: pathlib.Path,
    scale_bar: ScaleBar | None,
    support_min: float | None,
    support_enabled: bool,
) -> None:
    """Five circular annotation renders produce identical bytes."""
    first = _ref_render_annotated(fixture, scale_bar, support_min, support_enabled)
    for _ in range(4):
        again = _ref_render_annotated(fixture, scale_bar, support_min, support_enabled)
        assert again == first, f"circular annotation drift on {fixture.name}"


@pytest.mark.parametrize(
    "fixture,scale_bar,support_min,support_enabled",
    ANNOTATION_SPECS,
    ids=[s[0].name for s in ANNOTATION_SPECS],
)
def test_circular_annotation_matches_golden(
    fixture: pathlib.Path,
    scale_bar: ScaleBar | None,
    support_min: float | None,
    support_enabled: bool,
) -> None:
    """Circular annotation render matches the checked-in golden."""
    rendered = _ref_render_annotated(fixture, scale_bar, support_min, support_enabled)
    golden = GOLDEN_DIR / f"{fixture.stem}_annotated_circular.svg"
    if os.environ.get("UPDATE_GOLDENS") == "1":
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        golden.write_text(rendered)
        pytest.skip(f"updated golden {golden.name}")
    if not golden.exists():
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        golden.write_text(rendered)
        pytest.fail(
            f"circular annotation golden {golden.name} did not exist; created it. Re-run."
        )
    expected = golden.read_text()
    assert rendered == expected, (
        f"circular annotation golden mismatch on {fixture.name}; "
        f"set UPDATE_GOLDENS=1 to regenerate if intentional"
    )


@pytest.mark.skipif(
    not HAVE_CONNECTOR,
    reason="treescape_connector not built (run pip install -e ./treescape-connector)",
)
@pytest.mark.parametrize(
    "fixture,scale_bar,support_min,support_enabled",
    ANNOTATION_SPECS,
    ids=[s[0].name for s in ANNOTATION_SPECS],
)
def test_rust_circular_annotation_matches_ref_bytes(
    fixture: pathlib.Path,
    scale_bar: ScaleBar | None,
    support_min: float | None,
    support_enabled: bool,
) -> None:
    """Rust circular annotation SVG byte-identical to the Python ref."""
    src = fixture.read_text()
    rust_svg = rust_render_circular(
        RustTree.parse_newick(src),
        None,
        [],  # no highlights
        {},  # no tip colors
        [],  # no branch colors
        (scale_bar.length, scale_bar.label) if scale_bar else None,
        support_enabled,
        support_min,
    )
    ref_svg = _ref_render_annotated(fixture, scale_bar, support_min, support_enabled)
    assert rust_svg == ref_svg, (
        f"Rust/ref circular annotation diverged on {fixture.name}: "
        f"rust_len={len(rust_svg)} ref_len={len(ref_svg)}"
    )


@pytest.mark.parametrize("name,newick,support_min", SUPPORT_LABEL_NEWICKS)
def test_circular_support_labels_render(
    name: str, newick: str, support_min: float | None
) -> None:
    """Internal-node names render as upright middle-anchored Text on
    circular layout. min_value filter (when set) excludes nodes whose
    name parses below the threshold."""
    svg = _ref_render_from_newick(newick, None, support_min, support_enabled=True)
    if support_min is None:
        assert ">inner</text>" in svg
        assert ">other</text>" in svg
    else:
        assert ">95</text>" in svg
        assert ">50</text>" not in svg


def test_circular_scale_bar_anchored_at_canvas_right_edge() -> None:
    """Convention assertion: bar_x2 == canvas_width - padding (bar
    sits in the bottom-right corner, extending leftward)."""
    src = (FIXTURES_DIR / "small" / "balanced_4.nwk").read_text()
    tree = ref_parse(src)
    opts = SceneOptions()
    style = StyleSpec(scale_bar=ScaleBar(length=0.5, label="0.5"))
    scene = build_circular_scene(tree, opts, style=style)
    # The rendered SVG carries the scale-bar Line; the rightmost x2 of
    # the horizontal bar is the bar_x2 we want to assert. Pull it from
    # the scene graph directly to avoid SVG-string parsing.
    from treescape_reference.scene import Line, Text

    horizontals = [
        item
        for item in scene.items
        if isinstance(item, Line) and abs(item.y1 - item.y2) < 1e-9
    ]
    # Last horizontal Line is the scale bar (radial branches are also
    # Lines but with non-zero (x1, y1) → (x2, y2) deltas; the scale
    # bar is the only purely horizontal Line in the scene).
    assert horizontals, "no horizontal scale-bar Line found"
    bar = horizontals[-1]
    expected_bar_x2 = scene.canvas.width - opts.padding
    assert abs(bar.x2 - expected_bar_x2) < 1e-9, (
        f"scale bar bar_x2 = {bar.x2}, expected canvas_width - padding = {expected_bar_x2}"
    )


def test_circular_support_label_rotation_deg_is_zero_and_anchor_middle() -> None:
    """Convention assertion: support labels are upright (rotation_deg == 0)
    and middle-anchored."""
    from treescape_reference.scene import Text, TextAnchor

    tree = ref_parse("((a:1,b:1)inner:1,(c:1,d:1)other:1);")
    style = StyleSpec(support_labels=SupportLabelSpec())
    scene = build_circular_scene(tree, SceneOptions(), style=style)
    support_labels = [
        item
        for item in scene.items
        if isinstance(item, Text)
        and not item.is_tip_label
        and item.text in {"inner", "other"}
    ]
    assert len(support_labels) == 2, f"expected 2 support labels, got {len(support_labels)}"
    for label in support_labels:
        assert abs(label.rotation_deg) < 1e-9, (
            f"support label '{label.text}' rotation_deg = {label.rotation_deg}, expected 0"
        )
        assert label.anchor == TextAnchor.MIDDLE, (
            f"support label '{label.text}' anchor = {label.anchor}, expected MIDDLE"
        )


@pytest.fixture(scope="session", autouse=True)
def _emit_report() -> None:
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-circular-annotation-determinism",
        "version": "0.4",
        "timestamp_utc": int(time.time()),
        "tier": "ci",
        "fixtures": [s[0].name for s in ANNOTATION_SPECS],
        "modes": [
            "repeated_render",
            "golden_snapshot",
            "rust_vs_ref_bytes",
            "convention_bar_x2",
            "convention_support_rotation_anchor",
            "min_value_filter",
        ],
    }
    (REPORT_DIR / "circular_annotations.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
