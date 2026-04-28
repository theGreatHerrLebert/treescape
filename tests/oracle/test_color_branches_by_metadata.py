"""Oracle runner for claim ``treescape-color-branches-by-monophyly``."""

from __future__ import annotations

import json
import time
import warnings
from pathlib import Path

import pytest

pl = pytest.importorskip("polars", reason="polars required for metadata branch coloring claim")
pytest.importorskip(
    "treescape_connector.py_render",
    reason="treescape_connector not built (run pip install -e ./treescape-connector)",
)

from treescape import TreePlot, TreescapeStyleWarning


REPORT_DIR = Path(__file__).parent / "reports"
TREE = "((a:1,b:1)left_node:1,(c:1,d:1)right_node:1);"
PALETTE = {"left": "#ff0000", "right": "#0000ff"}


def test_branch_coloring_monophyletic_clades_do_not_warn() -> None:
    df = pl.DataFrame({"tip": ["a", "b", "c", "d"], "clade": ["left", "left", "right", "right"]})
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        svg = TreePlot(TREE).join_metadata(df, on="tip").color_branches_by(
            "clade",
            palette=PALETTE,
        ).to_svg()

    assert not [w for w in record if issubclass(w.category, TreescapeStyleWarning)]
    assert 'stroke="#ff0000"' in svg
    assert 'stroke="#0000ff"' in svg


def test_branch_coloring_paraphyletic_clade_warns_and_leaves_default() -> None:
    df = pl.DataFrame({"tip": ["a", "b", "c", "d"], "clade": ["left", "right", "right", "right"]})
    with pytest.warns(TreescapeStyleWarning, match="left_node"):
        svg = TreePlot(TREE).join_metadata(df, on="tip").color_branches_by(
            "clade",
            palette=PALETTE,
        ).to_svg()

    assert 'stroke="#0000ff"' in svg
    assert 'stroke="#ff0000"' not in svg
    assert 'stroke="#000000"' in svg


def test_branch_coloring_missing_value_warns_and_leaves_default() -> None:
    df = pl.DataFrame({"tip": ["a", "c", "d"], "clade": ["left", "right", "right"]})
    with pytest.warns(TreescapeStyleWarning, match="left_node"):
        svg = TreePlot(TREE).join_metadata(df, on="tip").color_branches_by(
            "clade",
            palette=PALETTE,
        ).to_svg()

    assert 'stroke="#0000ff"' in svg
    assert 'stroke="#ff0000"' not in svg


def test_branch_coloring_default_palette_is_deterministic() -> None:
    df = pl.DataFrame({"tip": ["d", "c", "b", "a"], "clade": ["right", "right", "left", "left"]})
    svg1 = TreePlot(TREE).join_metadata(df, on="tip").color_branches_by("clade").to_svg()
    svg2 = TreePlot(TREE).join_metadata(df, on="tip").color_branches_by("clade").to_svg()

    assert svg1 == svg2
    assert "#4e79a7" in svg1
    assert "#f28e2b" in svg1


@pytest.fixture(scope="session", autouse=True)
def _emit_report() -> None:
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-color-branches-by-monophyly",
        "version": "0.3",
        "timestamp_utc": int(time.time()),
        "tier": "ci",
    }
    (REPORT_DIR / "color_branches_by_metadata.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
