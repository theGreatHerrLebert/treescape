"""Oracle runner for claim ``treescape-orientation-transform``.

For every tree of ``layout-v2`` and every orientation, the Rust SVG must
draw each branch segment and each tip label where the documented
transform (``docs/conventions.md``, "Orientation") puts the node's
rectangular layout coordinate. The expected positions are computed here,
from the Rust layout and the formulas in the conventions, not by calling
the transform under test. Positions are compared as the SVG writes them
(four decimals). The Python reference must render the same bytes.

Goldens of an annotated tree (highlight, tip colours, support labels,
scale bar) in each orientation guard the items the position check does
not cover. Rotated text must pivot on its own anchor point.
"""

from __future__ import annotations

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter

import pytest

from _julia import REPO
from _layouts import LAYOUT_CORPUS
from treescape_reference.newick import parse as ref_parse
from treescape_reference.render import SceneOptions as RefSceneOptions
from treescape_reference.render import _fmt_f as fmt
from treescape_reference.render import build_rectangular_scene, render_svg

py_render = pytest.importorskip("treescape_connector.py_render", reason="treescape_connector not built")
from treescape_connector.py_layout import rectangular_layout  # noqa: E402
from treescape_connector.py_tree import Tree  # noqa: E402

REPORT_DIR = REPO / "tests" / "oracle" / "reports"
GOLDEN_DIR = REPO / "tests" / "fixtures" / "golden" / "orientation"
ORIENTATIONS = ("right", "down", "left", "up")
SVG = "{http://www.w3.org/2000/svg}"
# SceneOptions defaults (docs/conventions.md; pinned by the golden claims).
PAD, KX, KY, FONT, OFFSET = 12.0, 60.0, 18.0, 12.0, 4.0
CASES = [(f, o) for f in LAYOUT_CORPUS for o in ORIENTATIONS]
CHECKED: Counter = Counter()


def _transform(o: str, w: float):
    """The conventions table, written out independently."""
    return {
        "right": lambda x, y: (x, y),
        "left": lambda x, y: (w - x, y),
        "down": lambda x, y: (y, x),
        "up": lambda x, y: (y, w - x),
    }[o]


def _expected_anchor(o: str) -> tuple[str, str | None]:
    """(text-anchor, rotation) of a tip label."""
    return {"right": ("start", None), "left": ("end", None), "down": ("end", "-90"), "up": ("start", "-90")}[o]


def _drawn(svg: str):
    root = ET.fromstring(svg.encode())
    lines = Counter(
        (e.get("x1"), e.get("y1"), e.get("x2"), e.get("y2")) for e in root.iter(f"{SVG}line")
    )
    texts = {}
    for e in root.iter(f"{SVG}text"):
        rotation = None
        if e.get("transform"):
            # rotate(deg cx cy): the pivot must be the text's own anchor point.
            deg, cx, cy = re.fullmatch(r"rotate\((\S+) (\S+) (\S+)\)", e.get("transform")).groups()
            assert (cx, cy) == (e.get("x"), e.get("y")), f"{e.text}: rotation pivot {(cx, cy)} is not the anchor"
            rotation = deg
        texts[e.text] = (e.get("x"), e.get("y"), e.get("text-anchor"), rotation)
    return float(root.get("width")), float(root.get("height")), lines, texts


def _right_canvas_width(tree) -> float:
    """``W`` from its formula (docs/conventions.md: padding, depth span,
    label offset, widest tip label), checked against the "right" scene.
    The SVG header rounds it, and ``W - x`` needs it exact."""
    xs = rectangular_layout(tree).x
    names = [tree.name(i) for i in range(tree.n_nodes) if tree.is_tip(i)]
    widest = max((py_render.text_width(n, FONT) for n in names), default=0.0)
    w = PAD * 2 + (max(xs) - min(min(xs), 0.0)) * KX + OFFSET + widest
    assert w == py_render.build_rectangular_scene(tree).canvas_width
    return w


def _expected(tree, o: str, w: float):
    layout = rectangular_layout(tree)
    xs, ys = layout.x, layout.y
    min_x = min(min(xs), 0.0)
    t = _transform(o, w)

    def px(i: int) -> tuple[float, float]:
        return PAD + (xs[i] - min_x) * KX, PAD + ys[i] * KY

    def seg(a, b):
        (x1, y1), (x2, y2) = t(*a), t(*b)
        return (fmt(x1), fmt(y1), fmt(x2), fmt(y2))

    lines: Counter = Counter()
    texts = {}
    anchor, rotation = _expected_anchor(o)
    for i in tree.preorder():
        children = tree.children(i)
        if children:
            node_x = px(i)[0]
            cys = [px(c)[1] for c in children]
            lines[seg((node_x, min(cys)), (node_x, max(cys)))] += 1
            for c in children:
                cx, cy = px(c)
                lines[seg((node_x, cy), (cx, cy))] += 1
        elif tree.name(i):
            x, y = px(i)
            lx, ly = t(x + OFFSET, y + FONT * 0.35)
            texts[tree.name(i)] = (fmt(lx), fmt(ly), anchor, rotation)
    return lines, texts


@pytest.mark.parametrize("path,orientation", CASES, ids=[f"{p.parent.name}/{p.name}-{o}" for p, o in CASES])
def test_drawn_positions_follow_the_transform(path, orientation) -> None:
    src = path.read_text()
    tree = Tree.parse_newick(src)
    right_w = _right_canvas_width(tree)
    right_h = py_render.build_rectangular_scene(tree).canvas_height
    svg = py_render.render_rectangular_svg(tree, py_render.SceneOptions(orientation=orientation))
    w, h, lines, texts = _drawn(svg)
    expected_canvas = (right_w, right_h) if orientation in ("right", "left") else (right_h, right_w)
    assert (w, h) == tuple(float(fmt(v)) for v in expected_canvas)
    exp_lines, exp_texts = _expected(tree, orientation, right_w)
    assert lines == exp_lines, f"{path.name}/{orientation}: segments differ: {(lines - exp_lines) + (exp_lines - lines)}"
    assert texts == exp_texts, f"{path.name}/{orientation}: tip labels differ"
    ref_svg = render_svg(build_rectangular_scene(ref_parse(src), RefSceneOptions(orientation=orientation)))
    assert svg == ref_svg, f"{path.name}/{orientation}: Rust and reference bytes differ"
    CHECKED[orientation] += 1


SUPPORT_TREE = "((a:0.1,b:0.2)95:0.3,(c:0.15,(d:0.05,e:0.07)70:0.1)88:0.2);"


def _annotated(orientation: str) -> str:
    """Every annotation at once: highlight, tip colours, support labels
    (this tree has support values; primates.nwk has none) and a scale bar
    whose label is wider than the bar."""
    from treescape import TreePlot

    svg = (
        TreePlot(SUPPORT_TREE)
        .orientation(orientation)
        .options(px_per_x=300)
        .highlight_clade(["d", "e"], color="#ffb84d", alpha=0.35)
        .color_tips({"a": "#1f77b4", "c": "#d62728"})
        .support_labels()
        .scale_bar(0.05, "0.05 substitutions/site")
        .to_svg()
    )
    for text in (">95<", ">70<", ">88<", ">0.05 substitutions/site<", "<rect "):
        assert text in svg, f"{orientation}: {text} missing"
    return svg


@pytest.mark.parametrize("orientation", ORIENTATIONS)
def test_annotated_golden(orientation) -> None:
    rendered = _annotated(orientation)
    golden = GOLDEN_DIR / f"support_annotated_{orientation}.svg"
    if os.environ.get("UPDATE_GOLDENS") == "1":
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        golden.write_text(rendered)
        pytest.skip(f"updated golden {golden.name}")
    assert golden.exists(), f"missing {golden.name}; run with UPDATE_GOLDENS=1 once, then review it"
    assert rendered == golden.read_text(), f"golden mismatch: {golden.name}"


def test_circular_rejects_other_orientations() -> None:
    from treescape import TreePlot

    with pytest.raises(ValueError, match="rectangular layout only"):
        TreePlot("((a:1,b:1):1,c:2);").orientation("down").layout("circular").to_svg()
    with pytest.raises(ValueError, match="orientation must be one of"):
        TreePlot("(a,b);").orientation("top")


@pytest.fixture(scope="session", autouse=True)
def _emit_report():
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-orientation-transform",
        "version": "0.7",
        "timestamp_utc": int(time.time()),
        "trees": len(LAYOUT_CORPUS),
        "checked_per_orientation": dict(CHECKED),
    }
    (REPORT_DIR / "orientation.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
