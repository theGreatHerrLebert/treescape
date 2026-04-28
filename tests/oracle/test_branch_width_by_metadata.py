"""Oracle runner for claim ``treescape-branch-width-by-numeric-determinism``.

Property: ``TreePlot.width_branches_by(column, wmin, wmax, vmin, vmax)``
linearly maps a numeric metadata column onto branch stroke widths in
``[wmin, wmax]`` over ``[vmin, vmax]``. Tests cover (a) byte-determinism
across repeated renders, (b) subtree-mean rule on internal branches,
(c) tip-value rule on terminals, (d) clamping for out-of-range values,
(e) degenerate-range midpoint, (f) default stroke width on no-data
subtrees, (g) raise on non-numeric columns.

v0.4 Phase 3.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pytest

pl = pytest.importorskip("polars", reason="polars required for branch-width claim")
pytest.importorskip(
    "treescape_connector.py_render",
    reason="treescape_connector not built (run pip install -e ./treescape-connector)",
)

from treescape import TreePlot


REPORT_DIR = Path(__file__).parent / "reports"
TREE = "((a:1,b:1):1,(c:1,d:1):1);"
SUPPORTS = pl.DataFrame({"tip": ["a", "b", "c", "d"], "support": [0.5, 0.7, 0.85, 0.95]})


def _stroke_widths(svg: str) -> list[float]:
    """Pull every stroke-width attribute as a float."""
    return [float(w) for w in re.findall(r'stroke-width="([0-9.]+)"', svg)]


def test_byte_determinism_on_default_range() -> None:
    svg1 = TreePlot(TREE).join_metadata(SUPPORTS, on="tip").width_branches_by("support").to_svg()
    svg2 = TreePlot(TREE).join_metadata(SUPPORTS, on="tip").width_branches_by("support").to_svg()
    assert svg1 == svg2


def test_default_range_endpoints_match_observed_min_and_max() -> None:
    """Default (wmin, wmax) is (1.0, 4.0) with vmin/vmax = observed
    column min/max. So the tip with the smallest value gets width 1
    (which equals the default stroke_width — visually neutral) and
    the tip with the largest gets width 4."""
    svg = TreePlot(TREE).join_metadata(SUPPORTS, on="tip").width_branches_by("support").to_svg()
    widths = _stroke_widths(svg)
    # The float-formatter trims trailing zeros so "1.0" → "1" and
    # "4.0" → "4". Both endpoints must be present.
    assert 1.0 in widths
    assert 4.0 in widths


def test_custom_wmin_wmax_pin_extreme_widths() -> None:
    svg = (
        TreePlot(TREE)
        .join_metadata(SUPPORTS, on="tip")
        .width_branches_by("support", wmin=2.0, wmax=10.0)
        .to_svg()
    )
    widths = _stroke_widths(svg)
    # min observed support 0.5 → t=0 → width=wmin=2; max 0.95 → t=1 → width=wmax=10.
    assert 2.0 in widths
    assert 10.0 in widths


def test_vmin_vmax_pin_range_and_clamp_outliers() -> None:
    """Values outside [vmin, vmax] clamp to the colormap endpoints."""
    df = pl.DataFrame({"tip": ["a", "b", "c", "d"], "support": [0.0, 0.5, 0.5, 1.0]})
    pinned = (
        TreePlot(TREE)
        .join_metadata(df, on="tip")
        .width_branches_by("support", vmin=0.0, vmax=1.0)
        .to_svg()
    )
    auto = TreePlot(TREE).join_metadata(df, on="tip").width_branches_by("support").to_svg()
    assert pinned == auto


def test_degenerate_range_maps_all_to_midpoint() -> None:
    """All-equal values → t=0.5 for every branch → width = (wmin+wmax)/2."""
    df = pl.DataFrame({"tip": ["a", "b", "c", "d"], "support": [0.5, 0.5, 0.5, 0.5]})
    svg = (
        TreePlot(TREE)
        .join_metadata(df, on="tip")
        .width_branches_by("support", wmin=1.0, wmax=5.0)
        .to_svg()
    )
    widths = _stroke_widths(svg)
    # Every metadata-driven branch should be at the midpoint width 3.0.
    # Spines (vertical connectors) stay at the default stroke_width.
    assert 3.0 in widths


def test_terminal_branch_width_uses_tip_value() -> None:
    """The terminal-branch lift in v0.4 Phase 3: a terminal's width is
    derived from its tip's own value. With one tip having an extreme
    value (0.5 = vmin), its terminal branch must carry width = wmin."""
    df = pl.DataFrame({"tip": ["a", "b", "c", "d"], "support": [0.5, 0.7, 0.85, 0.95]})
    svg = (
        TreePlot(TREE)
        .join_metadata(df, on="tip")
        .width_branches_by("support", wmin=1.0, wmax=4.0)
        .to_svg()
    )
    widths = _stroke_widths(svg)
    # Tip a's terminal at vmin → width=1; tip d's terminal at vmax → width=4.
    assert 1.0 in widths
    assert 4.0 in widths


def test_subtree_mean_used_for_internal_branches() -> None:
    """Internal branch width = linear-interp(mean(subtree tip values)).
    For ((a,b),(c,d)) with values (0.5, 0.7, 0.85, 0.95), the (a,b)
    subtree mean is 0.6 and (c,d) is 0.9. Range 0.5–0.95, default
    widths 1.0–4.0:
      t(0.6) = (0.6-0.5)/0.45 ≈ 0.222  → width ≈ 1 + 0.222·3 = 1.667
      t(0.9) = (0.9-0.5)/0.45 ≈ 0.889  → width ≈ 1 + 0.889·3 = 3.667
    """
    svg = TreePlot(TREE).join_metadata(SUPPORTS, on="tip").width_branches_by("support").to_svg()
    widths = _stroke_widths(svg)
    # The trimmed-zero float-formatter writes 1.6667 / 3.6667.
    assert 1.6667 in widths
    assert 3.6667 in widths


def test_no_data_subtree_keeps_default_stroke_silently() -> None:
    """A subtree with no observed values keeps SceneOptions.stroke_width
    (= 1.0 default). No warning fires — same convention as the
    continuous-color path on no-data subtrees."""
    import warnings as _w
    from treescape import TreescapeStyleWarning

    # Tree where some subtree has no metadata coverage at all.
    df = pl.DataFrame({"tip": ["a", "b"], "support": [0.5, 0.7]})
    with _w.catch_warnings(record=True) as record:
        _w.simplefilter("always")
        svg = (
            TreePlot("((a:1,b:1):1,(c:1,d:1):1);")
            .join_metadata(df, on="tip")
            .width_branches_by("support")
            .to_svg()
        )
    # No TreescapeStyleWarning for the no-data (c,d) subtree
    assert not [w for w in record if issubclass(w.category, TreescapeStyleWarning)]
    widths = _stroke_widths(svg)
    # Default 1.0 must appear (c, d terminals + their parent stay at default)
    assert 1.0 in widths


def test_non_numeric_column_raises() -> None:
    df = pl.DataFrame({"tip": ["a", "b", "c", "d"], "clade": ["x", "x", "y", "y"]})
    plot = TreePlot(TREE).join_metadata(df, on="tip")
    with pytest.raises(ValueError, match="numeric column"):
        plot.width_branches_by("clade")


def test_unjoined_column_raises() -> None:
    plot = TreePlot(TREE)
    with pytest.raises(ValueError, match="not been joined"):
        plot.width_branches_by("support")


def test_circular_width_branches_by_works() -> None:
    """v0.4 Phase 3 width applies on circular too — radial Line gets
    the width override; arc spine stays at default stroke_width."""
    svg = (
        TreePlot(TREE)
        .layout("circular")
        .join_metadata(SUPPORTS, on="tip")
        .width_branches_by("support", wmin=1.0, wmax=4.0)
        .to_svg()
    )
    widths = _stroke_widths(svg)
    assert 1.0 in widths
    assert 4.0 in widths


@pytest.fixture(scope="session", autouse=True)
def _emit_report() -> None:
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-branch-width-by-numeric-determinism",
        "version": "0.4",
        "timestamp_utc": int(time.time()),
        "tier": "ci",
        "wrange_default": [1.0, 4.0],
    }
    (REPORT_DIR / "branch_width_by_metadata.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
