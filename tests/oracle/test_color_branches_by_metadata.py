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
    """v0.4 Phase 3: paraphyletic INTERNAL branch warns + stays default.
    Terminal branches now carry their own monophyly-by-trivial color
    (1-tip subtree always satisfies the rule), so even when an internal
    is paraphyletic, the terminals beneath it can still be colored."""
    df = pl.DataFrame({"tip": ["a", "b", "c", "d"], "clade": ["left", "right", "right", "right"]})
    with pytest.warns(TreescapeStyleWarning, match="left_node"):
        svg = TreePlot(TREE).join_metadata(df, on="tip").color_branches_by(
            "clade",
            palette=PALETTE,
        ).to_svg()

    assert 'stroke="#0000ff"' in svg  # right_node monophyletic + b/c/d terminals
    assert 'stroke="#ff0000"' in svg  # terminal a (v0.4 Phase 3 lift)
    assert 'stroke="#000000"' in svg  # left_node paraphyletic default + spines


def test_branch_coloring_missing_value_warns_and_leaves_default() -> None:
    """v0.4 Phase 3: terminal whose value is None keeps default; other
    terminals carry their own values."""
    df = pl.DataFrame({"tip": ["a", "c", "d"], "clade": ["left", "right", "right"]})
    with pytest.warns(TreescapeStyleWarning, match="left_node"):
        svg = TreePlot(TREE).join_metadata(df, on="tip").color_branches_by(
            "clade",
            palette=PALETTE,
        ).to_svg()

    assert 'stroke="#0000ff"' in svg  # right_node + c/d terminals
    assert 'stroke="#ff0000"' in svg  # terminal a (its own value=left)
    # terminal b has no value → keeps default; left_node still warns + default
    assert 'stroke="#000000"' in svg


def test_branch_coloring_default_palette_is_deterministic() -> None:
    df = pl.DataFrame({"tip": ["d", "c", "b", "a"], "clade": ["right", "right", "left", "left"]})
    svg1 = TreePlot(TREE).join_metadata(df, on="tip").color_branches_by("clade").to_svg()
    svg2 = TreePlot(TREE).join_metadata(df, on="tip").color_branches_by("clade").to_svg()

    assert svg1 == svg2
    assert "#4e79a7" in svg1
    assert "#f28e2b" in svg1


def test_branch_coloring_circular_monophyletic_clades_do_not_warn() -> None:
    """v0.4 Phase 1: the monophyly + warn semantics carry over to
    circular layouts. Per the locked convention, the radial parent→child
    Line gets the color; the arc spine stays at the default stroke."""
    df = pl.DataFrame({"tip": ["a", "b", "c", "d"], "clade": ["left", "left", "right", "right"]})
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        svg = (
            TreePlot(TREE)
            .layout("circular")
            .join_metadata(df, on="tip")
            .color_branches_by("clade", palette=PALETTE)
            .to_svg()
        )
    assert not [w for w in record if issubclass(w.category, TreescapeStyleWarning)]
    assert 'stroke="#ff0000"' in svg
    assert 'stroke="#0000ff"' in svg


def test_branch_coloring_circular_paraphyletic_warns_and_leaves_default() -> None:
    """v0.4 Phase 3: same terminal-lift behavior on circular layouts.
    Paraphyletic internal warns + stays default; terminals beneath it
    carry their own values."""
    df = pl.DataFrame({"tip": ["a", "b", "c", "d"], "clade": ["left", "right", "right", "right"]})
    with pytest.warns(TreescapeStyleWarning, match="left_node"):
        svg = (
            TreePlot(TREE)
            .layout("circular")
            .join_metadata(df, on="tip")
            .color_branches_by("clade", palette=PALETTE)
            .to_svg()
        )
    assert 'stroke="#0000ff"' in svg  # right_node + b/c/d terminals
    assert 'stroke="#ff0000"' in svg  # terminal a (v0.4 Phase 3 lift)
    # circular default stroke is also #000000; left_node + arc spines
    assert 'stroke="#000000"' in svg


@pytest.fixture(scope="session", autouse=True)
def _emit_report() -> None:
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-color-branches-by-monophyly",
        "version": "0.4",
        "timestamp_utc": int(time.time()),
        "tier": "ci",
        "layouts": ["rectangular", "circular"],
    }
    (REPORT_DIR / "color_branches_by_metadata.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
