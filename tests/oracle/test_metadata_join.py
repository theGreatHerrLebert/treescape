"""Oracle runner for claim ``treescape-metadata-join-roundtrip``."""

from __future__ import annotations

import json
import pathlib
import time

import pytest

pl = pytest.importorskip("polars", reason="polars required for metadata join claim")
pytest.importorskip(
    "treescape_connector.py_render",
    reason="treescape_connector not built (run pip install -e ./treescape-connector)",
)

from treescape import TreePlot
from treescape_reference.metadata import join_metadata as ref_join_metadata


WORKSPACE = pathlib.Path(__file__).parent.parent.parent
REPORT_DIR = pathlib.Path(__file__).parent / "reports"
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


@pytest.mark.parametrize("tree,meta", FIXTURE_PAIRS, ids=lambda p: p.stem)
def test_metadata_join_matches_reference_on_fixtures(
    tree: pathlib.Path,
    meta: pathlib.Path,
) -> None:
    df = pl.read_csv(meta)
    plot = TreePlot(tree).join_metadata(df, on="tip")
    expected, _ = ref_join_metadata(plot._tree.tip_order(), df, on="tip")

    for tip in plot._tree.tip_order():
        assert plot._metadata_for(tip) == expected[tip]


def test_metadata_join_missing_tip_gets_none_values() -> None:
    df = pl.DataFrame({"tip": ["a"], "clade": ["x"], "support": [0.7]})
    plot = TreePlot("(a:1,b:1);").join_metadata(df, on="tip")
    expected, _ = ref_join_metadata(["a", "b"], df, on="tip")

    assert plot._metadata_for("a") == expected["a"]
    assert plot._metadata_for("b") == expected["b"]


def test_metadata_join_empty_frame_is_legal() -> None:
    df = pl.DataFrame(
        {
            "tip": pl.Series([], dtype=pl.String),
            "clade": pl.Series([], dtype=pl.String),
        }
    )
    plot = TreePlot("(a:1,b:1);").join_metadata(df, on="tip")

    assert plot._metadata_for("a") == {"clade": None}
    assert plot._metadata_for("b") == {"clade": None}


def test_metadata_join_empty_frame_matches_reference() -> None:
    df = pl.DataFrame(
        {
            "tip": pl.Series([], dtype=pl.String),
            "clade": pl.Series([], dtype=pl.String),
        }
    )
    plot = TreePlot("(a:1,b:1);").join_metadata(df, on="tip")
    expected, _ = ref_join_metadata(["a", "b"], df, on="tip")

    for tip in ["a", "b"]:
        assert plot._metadata_for(tip) == expected[tip]


def test_metadata_join_rejects_extra_rows() -> None:
    df = pl.DataFrame({"tip": ["a", "x"], "clade": ["x", "bad"]})
    with pytest.raises(ValueError, match="not a tree tip"):
        TreePlot("(a:1,b:1);").join_metadata(df, on="tip")
    with pytest.raises(ValueError, match="not a tree tip"):
        ref_join_metadata(["a", "b"], df, on="tip")


def test_metadata_join_rejects_duplicate_rows() -> None:
    df = pl.DataFrame({"tip": ["a", "a"], "clade": ["x", "y"]})
    with pytest.raises(ValueError, match="duplicate"):
        TreePlot("(a:1,b:1);").join_metadata(df, on="tip")
    with pytest.raises(ValueError, match="duplicate"):
        ref_join_metadata(["a", "b"], df, on="tip")


def test_metadata_join_chained_columns_and_collision() -> None:
    df1 = pl.DataFrame({"tip": ["a", "b"], "clade": ["x", "y"]})
    df2 = pl.DataFrame({"tip": ["a", "b"], "host": ["h1", "h2"]})
    plot = TreePlot("(a:1,b:1);").join_metadata(df1, on="tip").join_metadata(df2, on="tip")
    expected, columns = ref_join_metadata(["a", "b"], df1, on="tip")
    expected, _ = ref_join_metadata(
        ["a", "b"],
        df2,
        on="tip",
        existing_rows=expected,
        existing_columns=columns,
    )

    assert plot._metadata_for("a") == expected["a"]
    assert plot._metadata_for("b") == expected["b"]
    with pytest.raises(ValueError, match="collision"):
        plot.join_metadata(pl.DataFrame({"tip": ["a", "b"], "clade": ["u", "v"]}), on="tip")


@pytest.fixture(scope="session", autouse=True)
def _emit_report() -> None:
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-metadata-join-roundtrip",
        "version": "0.3",
        "timestamp_utc": int(time.time()),
        "fixtures": [tree.name for tree, _ in FIXTURE_PAIRS],
        "tier": "ci",
    }
    (REPORT_DIR / "metadata_join.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
