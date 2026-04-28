"""Readable rectangular phylogram renderer + deterministic SVG writer.

Mirrors ``treescape_core::layout::rectangular::build_rectangular_scene``
and ``treescape_render::svg::render_svg`` line-for-line so they can be
kept in sync. Used as the pre-Phase-4 oracle for the
``treescape-svg-determinism`` and ``treescape-tip-count-invariant``
claims, and (v0.2+) the ``treescape-text-width-vs-fontdue`` claim.

v0.2: tip-label width is measured via ``treescape_reference.text``
(fontTools HMTX read of the bundled DejaVu Sans). The Rust core does
the same via fontdue. Both should agree to floating-point precision.
The legacy 0.6-em monospace approximation is still reachable by
passing ``measure=monospace_measurer`` if needed for tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from .layout import rectangular_layout
from .newick import Tree
from .scene import (
    BLACK,
    Canvas,
    Color,
    Line,
    Scene,
    Text,
    TextAnchor,
)
from .text import text_width as _fontdue_text_width


@dataclass
class SceneOptions:
    px_per_x: float = 60.0
    px_per_y: float = 18.0
    padding: float = 12.0
    font_size: float = 12.0
    avg_glyph_width: float = 0.6
    label_offset: float = 4.0
    stroke: Color = BLACK
    stroke_width: float = 1.0
    label_color: Color = BLACK


def monospace_measurer(text: str, font_size: float, *, avg_glyph_width: float = 0.6) -> float:
    """Legacy 0.6-em fallback used by v0.1. Kept for parity testing
    against the pre-fontdue path."""
    return len(text) * font_size * avg_glyph_width


def build_rectangular_scene(
    tree: Tree,
    opts: SceneOptions | None = None,
    measure: Optional[Callable[[str, float], float]] = None,
) -> Scene:
    if opts is None:
        opts = SceneOptions()
    if measure is None:
        measure = _fontdue_text_width

    if tree.root is None:
        return Scene(canvas=Canvas(0.0, 0.0), items=[])

    coords = rectangular_layout(tree)
    nodes = tree.postorder()

    xs = [coords[id(n)][0] for n in nodes]
    ys = [coords[id(n)][1] for n in nodes]
    # Negative branch lengths can push cumulative x below zero. Shift
    # so the leftmost coord lands at the padding boundary.
    min_x = min(min(xs) if xs else 0.0, 0.0)
    max_x = max(xs) if xs else 0.0
    max_y = max(ys) if ys else 0.0

    tip_widths = [measure(n.name, opts.font_size) for n in nodes if n.is_tip()]
    max_label_px = max(tip_widths) if tip_widths else 0.0

    x_span = max(max_x - min_x, 0.0)
    canvas = Canvas(
        width=opts.padding * 2 + x_span * opts.px_per_x + opts.label_offset + max_label_px,
        height=opts.padding * 2 + max_y * opts.px_per_y,
    )

    def to_px_x(xv: float) -> float:
        return opts.padding + (xv - min_x) * opts.px_per_x

    items: List[object] = []

    # Branches: pre-order so parents are visited before children
    preorder = _preorder(tree.root)
    for node in preorder:
        if not node.children:
            continue
        parent_x = to_px_x(coords[id(node)][0])
        child_ys = [coords[id(c)][1] for c in node.children]
        min_cy = min(child_ys)
        max_cy = max(child_ys)

        items.append(
            Line(
                x1=parent_x,
                y1=opts.padding + min_cy * opts.px_per_y,
                x2=parent_x,
                y2=opts.padding + max_cy * opts.px_per_y,
                stroke=opts.stroke,
                stroke_width=opts.stroke_width,
            )
        )

        for child in node.children:
            cx = to_px_x(coords[id(child)][0])
            cy = opts.padding + coords[id(child)][1] * opts.px_per_y
            items.append(
                Line(
                    x1=parent_x,
                    y1=cy,
                    x2=cx,
                    y2=cy,
                    stroke=opts.stroke,
                    stroke_width=opts.stroke_width,
                )
            )

    # Tip labels in pre-order
    for node in preorder:
        if not node.is_tip() or not node.name:
            continue
        tx = to_px_x(coords[id(node)][0]) + opts.label_offset
        ty = opts.padding + coords[id(node)][1] * opts.px_per_y + opts.font_size * 0.35
        items.append(
            Text(
                x=tx,
                y=ty,
                text=node.name,
                font_size=opts.font_size,
                color=opts.label_color,
                anchor=TextAnchor.START,
                is_tip_label=True,
            )
        )

    return Scene(canvas=canvas, items=items)


SVG_VERSION = "1.1"
FONT_FAMILY = "DejaVu Sans, sans-serif"


def render_svg(scene: Scene) -> str:
    """Emit deterministic SVG bytes from a scene graph.

    Determinism rules — must match the Rust impl byte-for-byte where
    possible (the floating-point trim and color formatting routines
    are aligned).
    """
    out: List[str] = []
    out.append('<?xml version="1.0" encoding="UTF-8"?>\n')
    out.append(
        f'<svg height="{_fmt_f(scene.canvas.height)}" '
        f'version="{SVG_VERSION}" '
        f'viewBox="0 0 {_fmt_f(scene.canvas.width)} {_fmt_f(scene.canvas.height)}" '
        f'width="{_fmt_f(scene.canvas.width)}" '
        f'xmlns="http://www.w3.org/2000/svg">\n'
    )
    for item in scene.items:
        if isinstance(item, Line):
            out.append(
                f'  <line stroke="{_fmt_color(item.stroke)}" '
                f'stroke-width="{_fmt_f(item.stroke_width)}" '
                f'x1="{_fmt_f(item.x1)}" '
                f'x2="{_fmt_f(item.x2)}" '
                f'y1="{_fmt_f(item.y1)}" '
                f'y2="{_fmt_f(item.y2)}"/>\n'
            )
        elif isinstance(item, Text):
            out.append(
                f'  <text fill="{_fmt_color(item.color)}" '
                f'font-family="{FONT_FAMILY}" '
                f'font-size="{_fmt_f(item.font_size)}" '
                f'text-anchor="{item.anchor.value}" '
                f'x="{_fmt_f(item.x)}" '
                f'y="{_fmt_f(item.y)}">{_xml_escape(item.text)}</text>\n'
            )
    out.append("</svg>\n")
    return "".join(out)


def _fmt_f(v: float) -> str:
    s = f"{v:.4f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
        if s in ("", "-"):
            s = "0"
    if s == "-0":
        s = "0"
    return s


def _fmt_color(c: Color) -> str:
    if c.a == 255:
        return f"#{c.r:02x}{c.g:02x}{c.b:02x}"
    return f"rgba({c.r},{c.g},{c.b},{c.a / 255:.3f})"


_XML_ESCAPES = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;"}


def _xml_escape(s: str) -> str:
    return "".join(_XML_ESCAPES.get(c, c) for c in s)


def _preorder(root) -> list:
    out = []
    stack = [root]
    while stack:
        n = stack.pop()
        out.append(n)
        for c in reversed(n.children):
            stack.append(c)
    return out


__all__ = [
    "SceneOptions",
    "build_rectangular_scene",
    "render_svg",
    "FONT_FAMILY",
    "SVG_VERSION",
]
