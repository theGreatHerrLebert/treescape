"""Focused tests for the user-facing ``treescape.TreePlot`` grammar."""

from __future__ import annotations

import pathlib

import pytest

pytest.importorskip(
    "treescape_connector.py_render",
    reason="treescape_connector not built (run pip install -e ./treescape-connector)",
)
pl = pytest.importorskip("polars", reason="polars required for metadata API tests")

from treescape import TreePlot

WORKSPACE = pathlib.Path(__file__).parent.parent.parent


def test_options_chain_preserves_previous_overrides() -> None:
    plot = TreePlot("(a:1,b:1);")
    plot.options(label_offset=12.0, stroke_width=2.0)
    plot.options(font_size=18.0)

    assert plot._scene_opts.label_offset == 12.0
    assert plot._scene_opts.stroke_width == 2.0
    assert plot._scene_opts.font_size == 18.0
    assert plot._circular_opts.label_offset == 12.0
    assert plot._circular_opts.stroke_width == 2.0
    assert plot._circular_opts.font_size == 18.0


def test_scale_bar_renders_rectangular_svg() -> None:
    svg = TreePlot("(a:1,b:2);").scale_bar(0.5, "0.5 substitutions/site").to_svg()

    assert ">0.5 substitutions/site</text>" in svg
    assert 'text-anchor="middle"' in svg


def test_scale_bar_rejects_non_positive_lengths() -> None:
    with pytest.raises(ValueError, match="positive"):
        TreePlot("(a:1,b:2);").scale_bar(0)


def test_support_labels_render_internal_node_names() -> None:
    svg = TreePlot("((a:1,b:1)95:0.2,c:1);").support_labels().to_svg()

    assert ">95</text>" in svg


def test_support_labels_threshold_filters_numeric_names() -> None:
    svg = (
        TreePlot("((a:1,b:1)65:0.2,(c:1,d:1)95:0.2);")
        .support_labels(min_value=70)
        .to_svg()
    )

    assert ">95</text>" in svg
    assert ">65</text>" not in svg


def test_support_labels_reject_circular_for_now() -> None:
    with pytest.raises(NotImplementedError, match="support_labels"):
        TreePlot("((a:1,b:1)95:0.2,c:1);").support_labels().layout("circular").to_svg()


def test_color_branches_by_works_on_circular() -> None:
    """v0.4 Phase 1 lifted the circular .color_branches_by NIE. Branch
    color is applied to the radial parent→child Line; the arc spine
    stays at the default stroke per the locked convention."""
    df = pl.DataFrame({"tip": ["a", "b", "c"], "clade": ["x", "x", "y"]})
    svg = (
        TreePlot("((a:1,b:1)x:1,c:1)root;")
        .join_metadata(df, on="tip")
        .color_branches_by("clade", palette={"x": "#ff0000", "y": "#0000ff"})
        .layout("circular")
        .to_svg()
    )
    assert 'stroke="#ff0000"' in svg, "monophyletic x-clade branch should be colored"


def test_join_metadata_roundtrips_tip_rows() -> None:
    tree = WORKSPACE / "tests" / "fixtures" / "trees" / "small" / "balanced_4.nwk"
    meta = WORKSPACE / "tests" / "fixtures" / "metadata" / "small" / "balanced_4.csv"
    plot = TreePlot(tree).join_metadata(pl.read_csv(meta), on="tip")

    assert plot._metadata_for("a") == {"clade": "left", "support": 0.91}
    assert plot._metadata_for("d") == {"clade": "right", "support": 0.94}


def test_join_metadata_missing_tip_gets_none_values() -> None:
    plot = TreePlot("(a:1,b:1);").join_metadata(
        pl.DataFrame({"tip": ["a"], "clade": ["x"], "support": [0.7]}),
        on="tip",
    )

    assert plot._metadata_for("a") == {"clade": "x", "support": 0.7}
    assert plot._metadata_for("b") == {"clade": None, "support": None}


def test_join_metadata_rejects_extra_and_duplicate_rows() -> None:
    with pytest.raises(ValueError, match="not a tree tip"):
        TreePlot("(a:1,b:1);").join_metadata(
            pl.DataFrame({"tip": ["a", "x"], "clade": ["x", "bad"]}),
            on="tip",
        )

    with pytest.raises(ValueError, match="duplicate"):
        TreePlot("(a:1,b:1);").join_metadata(
            pl.DataFrame({"tip": ["a", "a"], "clade": ["x", "y"]}),
            on="tip",
        )


def test_join_metadata_chains_without_join_key_collision() -> None:
    plot = (
        TreePlot("(a:1,b:1);")
        .join_metadata(pl.DataFrame({"tip": ["a", "b"], "clade": ["x", "y"]}), on="tip")
        .join_metadata(pl.DataFrame({"tip": ["a", "b"], "host": ["h1", "h2"]}), on="tip")
    )

    assert plot._metadata_for("a") == {"clade": "x", "host": "h1"}


def test_join_metadata_rejects_metadata_column_collision() -> None:
    with pytest.raises(ValueError, match="collision"):
        (
            TreePlot("(a:1,b:1);")
            .join_metadata(pl.DataFrame({"tip": ["a", "b"], "clade": ["x", "y"]}), on="tip")
            .join_metadata(pl.DataFrame({"tip": ["a", "b"], "clade": ["u", "v"]}), on="tip")
        )


def test_color_tips_by_matches_explicit_tip_colors() -> None:
    df = pl.DataFrame({"tip": ["a", "b", "c", "d"], "clade": ["left", "left", "right", "right"]})
    palette = {"left": "#ff0000", "right": "#0000ff"}
    via_metadata = TreePlot("((a:1,b:1):1,(c:1,d:1):1);").join_metadata(df, on="tip").color_tips_by(
        "clade",
        palette=palette,
    )
    explicit = TreePlot("((a:1,b:1):1,(c:1,d:1):1);").color_tips(
        {"a": "#ff0000", "b": "#ff0000", "c": "#0000ff", "d": "#0000ff"}
    )

    assert via_metadata.to_svg() == explicit.to_svg()


def test_color_tips_by_uses_deterministic_default_palette() -> None:
    df = pl.DataFrame({"tip": ["a", "b"], "clade": ["x", "y"]})
    svg = TreePlot("(a:1,b:1);").join_metadata(df, on="tip").color_tips_by("clade").to_svg()

    assert "#4e79a7" in svg
    assert "#f28e2b" in svg
