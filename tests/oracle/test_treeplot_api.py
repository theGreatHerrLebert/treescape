"""Focused tests for the user-facing ``treescape.TreePlot`` grammar."""

from __future__ import annotations

import math
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


@pytest.mark.parametrize("length", [float("nan"), float("inf")])
def test_scale_bar_rejects_non_finite_lengths(length: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        TreePlot("(a:1,b:2);").scale_bar(length)


def test_highlight_alpha_clamps_when_alpha_times_255_overflows() -> None:
    plot = TreePlot("((a:1,b:1):1,c:1);").highlight_clade(["a", "b"], alpha=1e307)
    assert plot._highlights[0][1][3] == 255
    with pytest.raises(ValueError, match="finite"):
        TreePlot("((a:1,b:1):1,c:1);").highlight_clade(["a"], alpha=float("nan"))


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


def test_support_labels_works_on_circular() -> None:
    """v0.4 Phase 2 lifted the circular .support_labels NIE. Internal
    node names render as upright (rotation_deg=0) middle-anchored Text
    at the projected internal-node position."""
    svg = TreePlot("((a:1,b:1)95:0.2,c:1);").support_labels().layout("circular").to_svg()
    assert ">95</text>" in svg


def test_scale_bar_works_on_circular() -> None:
    """v0.4 Phase 2 lifted the circular .scale_bar NIE. The bar lives
    in the bottom-right quadrant of the canvas, with right endpoint at
    canvas_width − padding."""
    svg = TreePlot("(a:1,b:2);").layout("circular").scale_bar(0.5, "0.5 subs/site").to_svg()
    assert ">0.5 subs/site</text>" in svg
    assert 'text-anchor="middle"' in svg


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


@pytest.mark.parametrize("opts", [{"padding": float("nan")}, {"px_per_x": float("inf")}, {"font_size": 1e300}])
def test_non_finite_geometry_raises_instead_of_writing_nan(opts):
    """v0.5 review finding: NaN/inf options used to produce `NaN` / `inf`
    SVG attributes (invalid SVG). The emitter now rejects them."""
    with pytest.raises(RuntimeError, match="non-finite"):
        TreePlot("((a:1,b:1):1,c:1);").options(**opts).to_svg()


TEXTBOOK = [[0, 5, 9, 9, 8], [5, 0, 10, 10, 9], [9, 10, 0, 8, 7], [9, 10, 8, 0, 3], [8, 9, 7, 3, 0]]


def test_from_distances_builds_the_textbook_nj_tree() -> None:
    plot = TreePlot.from_distances(TEXTBOOK, list("abcde"))
    assert plot.to_newick() == "(d:2.0,e:1.0,(c:4.0,(a:2.0,b:3.0):3.0):2.0);"
    assert "<svg" in plot.layout("circular").to_svg()


def test_from_distances_accepts_numpy_and_matches_from_linkage() -> None:
    np = pytest.importorskip("numpy")
    hierarchy = pytest.importorskip("scipy.cluster.hierarchy")
    distance = pytest.importorskip("scipy.spatial.distance")
    d = np.array(TEXTBOOK, dtype=float)
    upgma = TreePlot.from_distances(d, list("abcde"), method="upgma").to_newick()
    z = hierarchy.linkage(distance.squareform(d), method="average")
    assert TreePlot.from_linkage(z, list("abcde")).to_newick() == upgma


@pytest.mark.parametrize(
    "matrix,labels,method,message",
    [
        (TEXTBOOK, list("abcde"), "wpgma", "method must be 'nj' or 'upgma'"),
        (TEXTBOOK[:4], list("abcd"), "nj", "row 0 has 5 entries"),
        (TEXTBOOK, list("abcd"), "nj", "4 labels for a 5 x 5 matrix"),
        ([[0, 1], [2, 0]], ["a", "b"], "nj", "D[0][1] = 1.0 but D[1][0] = 2.0"),
        ([[0, float("nan")], [float("nan"), 0]], ["a", "b"], "upgma", "D[0][1] is not finite"),
        ([[0, 1], [1, 0]], ["a", "a"], "nj", "duplicate label 'a'"),
    ],
)
def test_from_distances_rejects_bad_input(matrix, labels, method, message) -> None:
    with pytest.raises(ValueError, match=message.replace("[", r"\[").replace("]", r"\]")):
        TreePlot.from_distances(matrix, labels, method=method)


@pytest.mark.parametrize(
    "z,labels,message",
    [
        ([[0, 1, 2, 2], [0, 2, 2, 2]], ["a", "b", "c"], "linkage row 1 joins invalid clusters"),
        ([[0, 1, 2, 2], [3, 3, 2, 2]], ["a", "b", "c"], "linkage row 1 joins invalid clusters"),
        ([[0, 1, 2, 2], [2, 3, 2, 2]], ["a", "a", "c"], "duplicate label 'a'"),
        ([[0, 1, 2, 2]], ["a", "b", "c"], "a linkage matrix for 3 labels has 2 rows, got 1"),
    ],
)
def test_from_linkage_rejects_malformed_matrices(z, labels, message) -> None:
    with pytest.raises(ValueError, match=message):
        TreePlot.from_linkage(z, labels)


ALIGN = WORKSPACE / "tests" / "fixtures" / "alignments"


def test_distances_from_fasta_and_from_sequences() -> None:
    from treescape import distances

    d, labels = distances.from_fasta(ALIGN / "gaps_and_ambiguity.fasta", model="k2p")
    assert labels == ["s1", "s2", "s3", "s4"]
    # s1/s2: 10 usable columns (a gap and an N dropped), one transversion: P = 0, Q = 0.1.
    assert abs(d[0][1] - (-0.5 * math.log(0.9) - 0.25 * math.log(0.8))) < 1e-12
    assert d[0][3] == 0.0 and str(d[0][3]) == "0.0"
    records = distances.read_fasta(ALIGN / "protein.fasta")
    assert TreePlot.from_sequences(records, model="poisson").to_newick() == TreePlot.from_sequences(
        ALIGN / "protein.fasta", model="poisson"
    ).to_newick()


@pytest.mark.parametrize(
    "fixture,model,message",
    [
        ("unaligned.fasta", "p", "must be aligned"),
        ("saturated.fasta", "jc69", "is saturated for jc69"),
        ("no_overlap.fasta", "p", "share no column"),
        ("protein.fasta", "k2p", "not available for protein sequences"),
        ("boundary_jc69.fasta", "jc69", "is saturated for jc69"),
        ("boundary_k2p.fasta", "k2p", "are saturated for k2p"),
        ("invalid_character.fasta", "p", r"\"it's\\x01odd\" has '\?' at column 4"),
    ],
)
def test_distances_reject_bad_input(fixture, model, message) -> None:
    from treescape import distances

    with pytest.raises(ValueError, match=message):
        distances.from_fasta(ALIGN / fixture, model=model)


def test_sequence_inputs_and_alphabets() -> None:
    import warnings

    from treescape import TreescapeSequenceWarning, distances

    text = (ALIGN / "doubtful_protein.fasta").read_text()
    with pytest.warns(TreescapeSequenceWarning, match="alphabet='protein'"):
        auto, _ = distances.from_source(text, model="p")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        protein, labels = distances.from_source(text, model="p", alphabet="protein")
    assert labels == ["p1", "p2", "p3"] and auto != protein
    # Protein U (selenocysteine) is not definite: MKUWLLE / MKTWLLE differ nowhere usable.
    d, _ = distances.from_fasta(ALIGN / "protein_u.fasta", model="p")
    assert d[0][1] == 0.0 and abs(d[0][2] - 1 / 6) < 1e-15
    # A mapping, pairs and FASTA text give the same matrix.
    pairs = distances.read_fasta_text(text)
    assert distances.from_records(dict(pairs), alphabet="protein") == distances.from_records(pairs, alphabet="protein")
    with pytest.raises(TypeError, match="record 1"):
        distances.from_records([("a", "ACGT"), ("b",)])
    with pytest.raises(ValueError, match="alphabet must be"):
        distances.from_records(pairs, alphabet="dna")


def test_fasta_file_bare_cr_is_not_a_line_break(tmp_path) -> None:
    """Read without newline translation, as Julia reads the same file."""
    from treescape import distances

    path = tmp_path / "cr.fasta"
    path.write_bytes(b">a\rACGT\r>b\rACGA\r")
    assert distances.read_fasta(path) == [("a", "")]
    path.write_bytes(b">a\r\nACGT\r\n>b\r\nACGA\r\n")
    assert distances.read_fasta(path) == [("a", "ACGT"), ("b", "ACGA")]


@pytest.mark.parametrize("layout", ["rectangular", "circular"])
@pytest.mark.parametrize("label", ["0.05", "0.05 substitutions/site", "a much longer scale bar label than the bar"])
def test_scale_bar_label_stays_inside_the_canvas(layout, label) -> None:
    """v0.6 clipped a label wider than its bar (docs/conventions.md)."""
    import xml.etree.ElementTree as ET

    from treescape_connector.py_render import text_width

    svg = TreePlot("((a:1,b:1):1,(c:1,d:2):1);").layout(layout).options(px_per_x=20).scale_bar(0.5, label).to_svg()
    root = ET.fromstring(svg.encode())
    ns = "{http://www.w3.org/2000/svg}"
    (text,) = [t for t in root.iter(f"{ns}text") if t.text == label]
    x, w = float(text.get("x")), text_width(label, 12.0)
    assert text.get("text-anchor") == "middle"
    assert x - w / 2 >= 12.0 - 1e-3 and x + w / 2 <= float(root.get("width")) - 12.0 + 1e-3
