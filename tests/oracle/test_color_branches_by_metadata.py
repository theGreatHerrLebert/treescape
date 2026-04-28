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


def test_branch_coloring_missing_value_warns_only_on_partial_data_clades() -> None:
    """v0.4 review round 1: warn iff the branch is paraphyletic AND has
    at least one observed value. Internal left_node has [a:left, b:None]
    (partial data) → warns. Terminal b has all-missing data → silent
    default (matches the continuous-color "no data" convention)."""
    df = pl.DataFrame({"tip": ["a", "c", "d"], "clade": ["left", "right", "right"]})
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        svg = TreePlot(TREE).join_metadata(df, on="tip").color_branches_by(
            "clade",
            palette=PALETTE,
        ).to_svg()

    style_warnings = [w for w in record if issubclass(w.category, TreescapeStyleWarning)]
    matched = [str(w.message) for w in style_warnings]
    assert len(matched) == 1, f"expected exactly one TreescapeStyleWarning, got {matched}"
    assert "left_node" in matched[0]
    assert all("branch b " not in m for m in matched), (
        "terminal b is all-missing → must default silently, not warn"
    )

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


def test_branch_coloring_failed_call_leaves_prior_state_intact() -> None:
    """v0.4 review round 2 (F4): a failing .color_branches_by call must
    not mutate _branch_colors. The round-1 fix cleared the map at the
    top of the method — that destroyed prior styling on validation
    raises (e.g., missing palette entry). Round-2 fix: build into a
    local, assign at the end."""
    df1 = pl.DataFrame({"tip": ["a", "b", "c", "d"], "clade": ["left", "left", "right", "right"]})
    df2 = pl.DataFrame({"tip": ["a", "b", "c", "d"], "host": ["h1", "h2", "h2", "h2"]})

    plot = (
        TreePlot(TREE)
        .join_metadata(df1, on="tip")
        .join_metadata(df2, on="tip")
        .color_branches_by("clade", palette=PALETTE)
    )
    svg_before = plot.to_svg()
    assert 'stroke="#ff0000"' in svg_before
    assert 'stroke="#0000ff"' in svg_before

    # Now call .color_branches_by with a palette that's missing a value.
    # _resolve_discrete_palette raises BEFORE any iteration.
    with pytest.raises(ValueError, match="palette missing"):
        plot.color_branches_by("host", palette={"h1": "#aabbcc"})  # missing h2

    # After the failure, the prior clade colors must still be there.
    svg_after = plot.to_svg()
    assert svg_after == svg_before, "failed call clobbered prior branch colors"


def test_branch_coloring_chained_call_clears_stale_state() -> None:
    """v0.4 review round 1 (F1): a second .color_branches_by call must
    fully redefine the metadata-driven branch coloring. Without the
    explicit clear, branches that were monophyletic under the FIRST
    call but not under the SECOND would silently retain stale colors."""
    df1 = pl.DataFrame({"tip": ["a", "b", "c", "d"], "clade": ["left", "left", "right", "right"]})
    df2 = pl.DataFrame({"tip": ["a", "b", "c", "d"], "host": ["h1", "h2", "h2", "h2"]})

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", TreescapeStyleWarning)
        svg = (
            TreePlot(TREE)
            .join_metadata(df1, on="tip")
            .join_metadata(df2, on="tip")
            .color_branches_by("clade", palette=PALETTE)
            .color_branches_by("host", palette={"h1": "#aabbcc", "h2": "#ddeeff"})
            .to_svg()
        )

    # After the second call, only host-derived colors should appear.
    # Clade colors from the first call must have been cleared.
    assert "#aabbcc" in svg or "#ddeeff" in svg, "host palette did not apply"
    assert "#ff0000" not in svg, "stale clade red survived from first .color_branches_by"
    assert "#0000ff" not in svg, "stale clade blue survived from first .color_branches_by"


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
