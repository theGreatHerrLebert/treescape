"""Oracle runner for claim ``treescape-color-by-continuous-determinism``.

Property: same column values + same ``cmap`` + same range → byte-identical
SVG. Tests cover (a) byte-determinism across repeated renders, (b) the
default ``cmap="viridis"`` produces the pinned LUT endpoints at min/max,
(c) ``vmin`` / ``vmax`` pin the colormap range, (d) callable cmaps work,
(e) palette+cmap conflict raises, (f) all-equal-values + degenerate range
produce a deterministic midpoint color rather than a divide-by-zero.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

pl = pytest.importorskip("polars", reason="polars required for continuous-color claim")
pytest.importorskip(
    "treescape_connector.py_render",
    reason="treescape_connector not built (run pip install -e ./treescape-connector)",
)

from treescape import TreePlot


REPORT_DIR = Path(__file__).parent / "reports"
TREE = "((a:1,b:1):1,(c:1,d:1):1);"
SUPPORTS = pl.DataFrame({"tip": ["a", "b", "c", "d"], "support": [0.5, 0.7, 0.85, 0.95]})


def test_tip_continuous_byte_determinism() -> None:
    svg1 = TreePlot(TREE).join_metadata(SUPPORTS, on="tip").color_tips_by("support").to_svg()
    svg2 = TreePlot(TREE).join_metadata(SUPPORTS, on="tip").color_tips_by("support").to_svg()
    assert svg1 == svg2


def test_branch_continuous_byte_determinism() -> None:
    svg1 = (
        TreePlot(TREE).join_metadata(SUPPORTS, on="tip").color_branches_by("support").to_svg()
    )
    svg2 = (
        TreePlot(TREE).join_metadata(SUPPORTS, on="tip").color_branches_by("support").to_svg()
    )
    assert svg1 == svg2


def test_default_cmap_is_viridis_and_endpoints_match_lut() -> None:
    svg = TreePlot(TREE).join_metadata(SUPPORTS, on="tip").color_tips_by("support").to_svg()
    assert "#440154" in svg, "viridis t=0 endpoint missing"
    assert "#fde725" in svg, "viridis t=1 endpoint missing"


def test_vmin_vmax_pin_range_and_clamp_outliers() -> None:
    df = pl.DataFrame({"tip": ["a", "b", "c", "d"], "support": [0.0, 0.5, 0.5, 1.0]})
    pinned = (
        TreePlot(TREE)
        .join_metadata(df, on="tip")
        .color_tips_by("support", vmin=0.0, vmax=1.0)
        .to_svg()
    )
    auto = TreePlot(TREE).join_metadata(df, on="tip").color_tips_by("support").to_svg()
    assert pinned == auto

    clamped = (
        TreePlot(TREE)
        .join_metadata(df, on="tip")
        .color_tips_by("support", vmin=0.5, vmax=0.5)
        .to_svg()
    )
    midpoint = (
        TreePlot(TREE)
        .join_metadata(pl.DataFrame({"tip": ["a", "b", "c", "d"], "support": [1.0, 1.0, 1.0, 1.0]}), on="tip")
        .color_tips_by("support")
        .to_svg()
    )
    assert clamped == midpoint, "degenerate range should fall back to midpoint deterministically"


def test_callable_cmap_overrides_builtin() -> None:
    def red_only(t: float) -> str:
        return "#ff0000"

    svg = (
        TreePlot(TREE)
        .join_metadata(SUPPORTS, on="tip")
        .color_tips_by("support", cmap=red_only)
        .to_svg()
    )
    assert svg.count("#ff0000") >= 4
    assert "#440154" not in svg


def test_palette_and_cmap_conflict_raises() -> None:
    plot = TreePlot(TREE).join_metadata(SUPPORTS, on="tip")
    with pytest.raises(ValueError, match="palette= or cmap="):
        plot.color_tips_by("support", palette={0.5: "#fff"}, cmap="viridis")


def test_unknown_cmap_name_raises() -> None:
    plot = TreePlot(TREE).join_metadata(SUPPORTS, on="tip")
    with pytest.raises(ValueError, match="unknown cmap"):
        plot.color_tips_by("support", cmap="not_a_real_cmap")


def test_branch_continuous_skips_subtree_with_no_data_silently() -> None:
    df = pl.DataFrame({"tip": ["c", "d"], "support": [0.5, 0.95]})
    import warnings as _w

    with _w.catch_warnings(record=True) as record:
        _w.simplefilter("always")
        svg = (
            TreePlot(TREE)
            .join_metadata(df, on="tip")
            .color_branches_by("support")
            .to_svg()
        )
    from treescape import TreescapeStyleWarning

    assert not [w for w in record if issubclass(w.category, TreescapeStyleWarning)]
    assert len(svg) > 0


def test_missing_metadata_value_keeps_default_tip_color() -> None:
    df = pl.DataFrame({"tip": ["a", "b", "c"], "support": [0.0, 0.5, 1.0]})
    svg = TreePlot(TREE).join_metadata(df, on="tip").color_tips_by("support").to_svg()
    assert "#440154" in svg
    assert "#fde725" in svg
    assert 'fill="#000000"' in svg


def test_auto_detect_numeric_column_uses_viridis() -> None:
    svg = TreePlot(TREE).join_metadata(SUPPORTS, on="tip").color_tips_by("support").to_svg()
    explicit = (
        TreePlot(TREE)
        .join_metadata(SUPPORTS, on="tip")
        .color_tips_by("support", cmap="viridis")
        .to_svg()
    )
    assert svg == explicit


def test_circular_tip_continuous_byte_determinism_and_endpoints() -> None:
    """v0.4 Phase 1: continuous tip coloring carries over to circular
    layouts. Same byte-determinism property; same viridis LUT endpoints
    at the column's observed min/max."""
    svg1 = (
        TreePlot(TREE)
        .layout("circular")
        .join_metadata(SUPPORTS, on="tip")
        .color_tips_by("support")
        .to_svg()
    )
    svg2 = (
        TreePlot(TREE)
        .layout("circular")
        .join_metadata(SUPPORTS, on="tip")
        .color_tips_by("support")
        .to_svg()
    )
    assert svg1 == svg2
    assert "#440154" in svg1, "viridis t=0 endpoint missing on circular"
    assert "#fde725" in svg1, "viridis t=1 endpoint missing on circular"


def test_circular_branch_continuous_byte_determinism() -> None:
    svg1 = (
        TreePlot(TREE)
        .layout("circular")
        .join_metadata(SUPPORTS, on="tip")
        .color_branches_by("support")
        .to_svg()
    )
    svg2 = (
        TreePlot(TREE)
        .layout("circular")
        .join_metadata(SUPPORTS, on="tip")
        .color_branches_by("support")
        .to_svg()
    )
    assert svg1 == svg2


@pytest.fixture(scope="session", autouse=True)
def _emit_report() -> None:
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-color-by-continuous-determinism",
        "version": "0.4",
        "timestamp_utc": int(time.time()),
        "tier": "ci",
        "cmap": "viridis (treescape pinned 11-keystop LUT)",
        "layouts": ["rectangular", "circular"],
    }
    (REPORT_DIR / "color_by_continuous.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
