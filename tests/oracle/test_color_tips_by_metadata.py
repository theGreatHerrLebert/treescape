"""Oracle runner for claim ``treescape-color-tips-by-discrete-roundtrip``."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

pl = pytest.importorskip("polars", reason="polars required for metadata coloring claim")
pytest.importorskip(
    "treescape_connector.py_render",
    reason="treescape_connector not built (run pip install -e ./treescape-connector)",
)

from treescape import TreePlot


REPORT_DIR = Path(__file__).parent / "reports"
WORKSPACE = Path(__file__).parent.parent.parent
TREE = "((a:1,b:1):1,(c:1,d:1):1);"
FIXTURE_PAIRS = [
    (
        WORKSPACE / "tests" / "fixtures" / "trees" / "small" / "two_tip.nwk",
        WORKSPACE / "tests" / "fixtures" / "metadata" / "small" / "two_tip.csv",
    ),
    (
        WORKSPACE / "tests" / "fixtures" / "trees" / "small" / "balanced_4.nwk",
        WORKSPACE / "tests" / "fixtures" / "metadata" / "small" / "balanced_4.csv",
    ),
    (
        WORKSPACE / "tests" / "fixtures" / "trees" / "small" / "unbalanced_5.nwk",
        WORKSPACE / "tests" / "fixtures" / "metadata" / "small" / "unbalanced_5.csv",
    ),
]


def test_color_tips_by_discrete_matches_explicit_mapping() -> None:
    df = pl.DataFrame({"tip": ["a", "b", "c", "d"], "clade": ["left", "left", "right", "right"]})
    palette = {"left": "#ff0000", "right": "#0000ff"}
    via_metadata = TreePlot(TREE).join_metadata(df, on="tip").color_tips_by("clade", palette=palette)
    explicit = TreePlot(TREE).color_tips(
        {"a": "#ff0000", "b": "#ff0000", "c": "#0000ff", "d": "#0000ff"}
    )

    assert via_metadata.to_svg() == explicit.to_svg()


@pytest.mark.parametrize("tree,meta", FIXTURE_PAIRS, ids=lambda p: p.stem)
def test_color_tips_by_discrete_fixture_matches_explicit_mapping(
    tree: Path,
    meta: Path,
) -> None:
    df = pl.read_csv(meta)
    values = []
    for row in df.to_dicts():
        value = row["clade"]
        if value not in values:
            values.append(value)
    palette = {value: f"#{i + 1:02x}{i + 2:02x}{i + 3:02x}" for i, value in enumerate(values)}
    explicit_mapping = {row["tip"]: palette[row["clade"]] for row in df.to_dicts()}

    via_metadata = TreePlot(tree).join_metadata(df, on="tip").color_tips_by(
        "clade",
        palette=palette,
    )
    explicit = TreePlot(tree).color_tips(explicit_mapping)

    assert via_metadata.to_svg() == explicit.to_svg()


def test_default_palette_is_tree_order_deterministic() -> None:
    df = pl.DataFrame({"tip": ["d", "c", "b", "a"], "clade": ["right", "right", "left", "left"]})
    svg1 = TreePlot(TREE).join_metadata(df, on="tip").color_tips_by("clade").to_svg()
    svg2 = TreePlot(TREE).join_metadata(df, on="tip").color_tips_by("clade").to_svg()

    assert svg1 == svg2
    assert "#4e79a7" in svg1
    assert "#f28e2b" in svg1


def test_missing_metadata_values_keep_default_tip_color() -> None:
    df = pl.DataFrame({"tip": ["a"], "clade": ["left"]})
    svg = TreePlot("(a:1,b:1);").join_metadata(df, on="tip").color_tips_by("clade").to_svg()

    assert 'fill="#4e79a7"' in svg
    assert 'fill="#000000"' in svg


def test_palette_must_cover_observed_values() -> None:
    df = pl.DataFrame({"tip": ["a", "b"], "clade": ["x", "y"]})
    with pytest.raises(ValueError, match="palette missing"):
        TreePlot("(a:1,b:1);").join_metadata(df, on="tip").color_tips_by(
            "clade",
            palette={"x": "#ff0000"},
        )


@pytest.fixture(scope="session", autouse=True)
def _emit_report() -> None:
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-color-tips-by-discrete-roundtrip",
        "version": "0.3",
        "fixtures": [tree.name for tree, _ in FIXTURE_PAIRS],
        "timestamp_utc": int(time.time()),
        "tier": "ci",
    }
    (REPORT_DIR / "color_tips_by_metadata.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
