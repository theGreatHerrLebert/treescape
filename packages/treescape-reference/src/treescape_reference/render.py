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

import math
from dataclasses import dataclass, field
from typing import Dict, List as ListT

from .layout import circular_layout, clade_tips, find_mrca, rectangular_layout
from .newick import Tree
from .scene import (
    BLACK,
    AnnularSector,
    Arc,
    Canvas,
    Color,
    Line,
    Rect,
    Scene,
    Text,
    TextAnchor,
)
from .text import text_width as _fontdue_text_width


@dataclass(frozen=True)
class CladeHighlight:
    tip_names: tuple
    fill: Color


@dataclass(frozen=True)
class ScaleBar:
    """Branch-length scale bar. ``length`` is in the same units as
    Newick edge lengths."""

    length: float
    label: str


@dataclass(frozen=True)
class SupportLabelSpec:
    """Internal-node label rendering options. ``min_value`` filters
    numeric labels; nodes whose name doesn't parse as ``f64`` are
    skipped when ``min_value`` is set."""

    min_value: Optional[float] = None


@dataclass
class StyleSpec:
    """Style overrides shared by the rectangular and (v0.4 Phase 1+2)
    circular scene builders. Default = no styling; existing
    SVG bytes unchanged.

    `highlights` is a list (order-preserving — first highlight emits
    first, draws underneath any later highlights at the same location).
    `tip_colors` is a name→color map; missing names fall back to
    SceneOptions.label_color.
    `branch_colors` (v0.4 Phase 1) keys by Python node identity
    (``id(node)`` for the Python reference) and overrides the
    parent→child branch stroke — horizontal segment for rectangular,
    radial Line for circular. Sibling spines (rectangular vertical
    connector, circular arc) stay at the default stroke per the locked
    convention. Missing entries fall back to ``SceneOptions.stroke``.
    `scale_bar` and `support_labels` (v0.4 Phase 2 for circular;
    rectangular impl reserved for parallel parity work) attach the
    annotation features documented in ``docs/conventions.md``.
    """

    highlights: ListT[CladeHighlight] = field(default_factory=list)
    tip_colors: Dict[str, Color] = field(default_factory=dict)
    branch_colors: Dict[int, Color] = field(default_factory=dict)
    branch_widths: Dict[int, float] = field(default_factory=dict)
    scale_bar: Optional[ScaleBar] = None
    support_labels: Optional[SupportLabelSpec] = None


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
    style: StyleSpec | None = None,
) -> Scene:
    if opts is None:
        opts = SceneOptions()
    if measure is None:
        measure = _fontdue_text_width
    if style is None:
        style = StyleSpec()

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

    # Highlight rectangles emitted first so they render behind branches.
    for h in style.highlights:
        try:
            mrca = find_mrca(tree, list(h.tip_names))
        except (KeyError, ValueError):
            continue
        clade = clade_tips(tree, mrca)
        if not clade:
            continue
        tip_ys = [coords[id(n)][1] for n in clade]
        min_ty = min(tip_ys)
        max_ty = max(tip_ys)
        half_row = opts.px_per_y * 0.5
        rx = to_px_x(coords[id(mrca)][0])
        ry = opts.padding + min_ty * opts.px_per_y - half_row
        rw = canvas.width - rx - opts.padding
        rh = (max_ty - min_ty) * opts.px_per_y + 2.0 * half_row
        items.append(
            Rect(
                x=rx,
                y=ry,
                width=max(rw, 0.0),
                height=max(rh, 0.0),
                fill=h.fill,
            )
        )

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
            branch_stroke = style.branch_colors.get(id(child), opts.stroke)
            branch_width = style.branch_widths.get(id(child), opts.stroke_width)
            items.append(
                Line(
                    x1=parent_x,
                    y1=cy,
                    x2=cx,
                    y2=cy,
                    stroke=branch_stroke,
                    stroke_width=branch_width,
                )
            )

    # Tip labels in pre-order
    for node in preorder:
        if not node.is_tip() or not node.name:
            continue
        tx = to_px_x(coords[id(node)][0]) + opts.label_offset
        ty = opts.padding + coords[id(node)][1] * opts.px_per_y + opts.font_size * 0.35
        label_color = style.tip_colors.get(node.name, opts.label_color)
        items.append(
            Text(
                x=tx,
                y=ty,
                text=node.name,
                font_size=opts.font_size,
                color=label_color,
                anchor=TextAnchor.START,
                is_tip_label=True,
            )
        )

    return Scene(canvas=canvas, items=items)


def build_circular_scene(
    tree: Tree,
    opts: SceneOptions | None = None,
    measure: Optional[Callable[[str, float], float]] = None,
    *,
    start_angle: float = math.pi / 2,
    sweep_total: float = 2 * math.pi,
    style: StyleSpec | None = None,
) -> Scene:
    """Circular phylogram scene: radial branches, arc spines, rotated
    tip labels. Conventions in ``docs/conventions.md``.

    Per the locked convention, the canvas is square; the projection is
    ``x = cx + r·cos(θ); y = cy − r·sin(θ)``.

    v0.3 Phase 3: ``style.highlights`` emit ``AnnularSector`` items
    behind branches/labels. ``style.tip_colors`` and other style fields
    are reserved for future circular extensions and currently ignored
    on the circular path (the user-facing TreePlot still raises
    NotImplementedError for them).
    """
    if opts is None:
        opts = SceneOptions()
    if measure is None:
        measure = _fontdue_text_width
    if style is None:
        style = StyleSpec()

    if tree.root is None:
        return Scene(canvas=Canvas(0.0, 0.0), items=[])

    coords = circular_layout(tree, start_angle=start_angle, sweep_total=sweep_total)
    nodes = tree.postorder()

    rs = [coords[id(n)][0] for n in nodes if n.is_tip()]
    max_r = max(rs) if rs else 0.0

    # px_per_r reuses px_per_x (radial axis is the same metric as
    # rectangular's x). Canvas must fit a label sticking out radially
    # at any tip, so we expand by the widest tip label in any direction.
    tip_widths = [measure(n.name, opts.font_size) for n in nodes if n.is_tip()]
    max_label_px = max(tip_widths) if tip_widths else 0.0

    radius_px = max_r * opts.px_per_x
    half = opts.padding + radius_px + opts.label_offset + max_label_px
    canvas_size = 2.0 * half
    canvas = Canvas(width=canvas_size, height=canvas_size)
    cx = cy = half

    def project(r: float, theta: float) -> tuple[float, float]:
        return cx + r * opts.px_per_x * math.cos(theta), cy - r * opts.px_per_x * math.sin(theta)

    items: List[object] = []

    preorder = _preorder(tree.root)

    # Highlights (annular sectors) emitted first so they render behind
    # branches, arc spines, and labels. MRCA == root raises ValueError
    # rather than emitting a whole-canvas sector. Per docs/conventions.md
    # (v0.3 Phase 3), r_outer matches the canvas's tip-label zone so
    # every highlight extends to the same outer radius.
    r_outer_px = radius_px + opts.label_offset + max_label_px
    for h in style.highlights:
        try:
            mrca = find_mrca(tree, list(h.tip_names))
        except (KeyError, ValueError):
            continue
        if mrca is tree.root:
            raise ValueError(
                "circular highlight_clade(MRCA == root) covers the whole tree; "
                "drop the highlight or pick a deeper clade"
            )
        clade = clade_tips(tree, mrca)
        if not clade:
            continue
        tip_thetas = [coords[id(n)][1] for n in clade]
        theta_min = min(tip_thetas)
        theta_max = max(tip_thetas)
        r_inner_px = coords[id(mrca)][0] * opts.px_per_x
        items.append(
            AnnularSector(
                cx=cx,
                cy=cy,
                r_inner=r_inner_px,
                r_outer=r_outer_px,
                theta_min=theta_min,
                theta_max=theta_max,
                fill=h.fill,
            )
        )

    # Radial branch segments and arc spines.
    for node in preorder:
        if not node.children:
            continue
        parent_r = coords[id(node)][0]
        child_thetas = [coords[id(c)][1] for c in node.children]

        # One radial line per child, from (parent_r, child.θ) to (child.r, child.θ).
        # v0.4 Phase 1: branch_colors (keyed by Node identity for the
        # Python ref) override the radial line stroke. The arc spine
        # below stays at the default stroke per the locked convention
        # (docs/conventions.md, v0.4 Phase 1) — same idiom as
        # rectangular's vertical-spine-stays-default rule.
        for child in node.children:
            cr, cth = coords[id(child)]
            x1, y1 = project(parent_r, cth)
            x2, y2 = project(cr, cth)
            branch_stroke = style.branch_colors.get(id(child), opts.stroke)
            branch_width = style.branch_widths.get(id(child), opts.stroke_width)
            items.append(
                Line(
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    stroke=branch_stroke,
                    stroke_width=branch_width,
                )
            )

        # Arc spine connecting all children at radius=parent_r. Skip
        # for parent_r=0 (root): draw a single point, but actually
        # zero-radius arcs are degenerate; the radial lines from r=0
        # already meet at the origin.
        if parent_r > 0.0 and len(child_thetas) >= 2:
            min_th = min(child_thetas)
            max_th = max(child_thetas)
            span = max_th - min_th
            x1, y1 = project(parent_r, min_th)
            x2, y2 = project(parent_r, max_th)
            items.append(
                Arc(
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    radius=parent_r * opts.px_per_x,
                    large_arc=span > math.pi,
                    # Increasing θ = CCW visually in our SVG projection.
                    # We go from min_th to max_th, so SVG sweep=0 (CCW).
                    sweep_clockwise=False,
                    stroke=opts.stroke,
                    stroke_width=opts.stroke_width,
                )
            )

    # Tip labels: project to (r + label_offset_radial, θ); rotate so
    # text reads outward; flip anchor for left-half tips so labels
    # don't read upside down.
    for node in preorder:
        if not node.is_tip() or not node.name:
            continue
        r, theta = coords[id(node)]
        ux = math.cos(theta)
        uy = -math.sin(theta)  # SVG y-flip
        tip_proj_x, tip_proj_y = project(r, theta)
        tx = tip_proj_x + opts.label_offset * ux
        ty = tip_proj_y + opts.label_offset * uy

        deg = math.degrees(theta)
        if ux >= 0:
            anchor = TextAnchor.START
            rotation_deg = -deg
        else:
            anchor = TextAnchor.END
            rotation_deg = -deg + 180.0

        # v0.4 Phase 1: per-tip color override via style.tip_colors,
        # keyed by tip name (portable across Python ref / Rust). Same
        # mechanism the rectangular ref already uses.
        label_color = style.tip_colors.get(node.name, opts.label_color)
        items.append(
            Text(
                x=tx,
                y=ty,
                text=node.name,
                font_size=opts.font_size,
                color=label_color,
                anchor=anchor,
                is_tip_label=True,
                rotation_deg=rotation_deg,
            )
        )

    # v0.4 Phase 2: support labels — upright text at projected
    # internal-node positions (rotation_deg = 0), middle-anchored.
    # Per the locked convention, no offset from the projection.
    if style.support_labels is not None:
        spec = style.support_labels
        for node in preorder:
            if node.is_tip() or not node.name:
                continue
            if spec.min_value is not None:
                try:
                    value = float(node.name)
                except (TypeError, ValueError):
                    continue
                if value < spec.min_value:
                    continue
            r, theta = coords[id(node)]
            sx, sy = project(r, theta)
            items.append(
                Text(
                    x=sx,
                    y=sy,
                    text=node.name,
                    font_size=opts.font_size,
                    color=opts.label_color,
                    anchor=TextAnchor.MIDDLE,
                    is_tip_label=False,
                    rotation_deg=0.0,
                )
            )

    # v0.4 Phase 2: bottom-right radial scale bar. Per the locked
    # convention, the bar's right endpoint is anchored at
    # canvas_width - padding and it extends leftward; ticks at both
    # ends, label centered below.
    if style.scale_bar is not None and style.scale_bar.length > 0:
        bar_x2 = canvas.width - opts.padding
        bar_x1 = bar_x2 - style.scale_bar.length * opts.px_per_x
        bar_y = canvas.height - opts.padding - opts.font_size * 1.2
        tick = max(opts.font_size * 0.35, 3.0)
        items.append(
            Line(
                x1=bar_x1, y1=bar_y, x2=bar_x2, y2=bar_y,
                stroke=opts.stroke,
                stroke_width=opts.stroke_width,
            )
        )
        for tx_tick in (bar_x1, bar_x2):
            items.append(
                Line(
                    x1=tx_tick, y1=bar_y - tick * 0.5,
                    x2=tx_tick, y2=bar_y + tick * 0.5,
                    stroke=opts.stroke,
                    stroke_width=opts.stroke_width,
                )
            )
        items.append(
            Text(
                x=(bar_x1 + bar_x2) * 0.5,
                y=bar_y + opts.font_size * 1.2,
                text=style.scale_bar.label,
                font_size=opts.font_size,
                color=opts.label_color,
                anchor=TextAnchor.MIDDLE,
                is_tip_label=False,
                rotation_deg=0.0,
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
        if isinstance(item, Rect):
            out.append(
                f'  <rect fill="{_fmt_color(item.fill)}" '
                f'height="{_fmt_f(item.height)}" '
                f'width="{_fmt_f(item.width)}" '
                f'x="{_fmt_f(item.x)}" '
                f'y="{_fmt_f(item.y)}"/>\n'
            )
        elif isinstance(item, AnnularSector):
            # Project the four corners of the sector under the SVG y-flip.
            # M (inner, theta_min) L (outer, theta_min) A->outer-arc->
            # (outer, theta_max) L (inner, theta_max) A->inner-arc->
            # (inner, theta_min) Z. Outer arc sweep_flag=0 (CCW visually
            # under the y-flipped projection — same convention as the
            # circular Arc spine); inner arc sweep_flag=1 (return CW).
            cosmin = math.cos(item.theta_min)
            sinmin = math.sin(item.theta_min)
            cosmax = math.cos(item.theta_max)
            sinmax = math.sin(item.theta_max)
            ix0 = item.cx + item.r_inner * cosmin
            iy0 = item.cy - item.r_inner * sinmin
            ox0 = item.cx + item.r_outer * cosmin
            oy0 = item.cy - item.r_outer * sinmin
            ox1 = item.cx + item.r_outer * cosmax
            oy1 = item.cy - item.r_outer * sinmax
            ix1 = item.cx + item.r_inner * cosmax
            iy1 = item.cy - item.r_inner * sinmax
            la = 1 if (item.theta_max - item.theta_min) > math.pi else 0
            ro = _fmt_f(item.r_outer)
            ri = _fmt_f(item.r_inner)
            out.append(
                f'  <path d="M {_fmt_f(ix0)} {_fmt_f(iy0)} '
                f'L {_fmt_f(ox0)} {_fmt_f(oy0)} '
                f'A {ro} {ro} 0 {la} 0 {_fmt_f(ox1)} {_fmt_f(oy1)} '
                f'L {_fmt_f(ix1)} {_fmt_f(iy1)} '
                f'A {ri} {ri} 0 {la} 1 {_fmt_f(ix0)} {_fmt_f(iy0)} Z" '
                f'fill="{_fmt_color(item.fill)}"/>\n'
            )
        elif isinstance(item, Line):
            out.append(
                f'  <line stroke="{_fmt_color(item.stroke)}" '
                f'stroke-width="{_fmt_f(item.stroke_width)}" '
                f'x1="{_fmt_f(item.x1)}" '
                f'x2="{_fmt_f(item.x2)}" '
                f'y1="{_fmt_f(item.y1)}" '
                f'y2="{_fmt_f(item.y2)}"/>\n'
            )
        elif isinstance(item, Arc):
            la = 1 if item.large_arc else 0
            sw = 1 if item.sweep_clockwise else 0
            r = _fmt_f(item.radius)
            out.append(
                f'  <path d="M {_fmt_f(item.x1)} {_fmt_f(item.y1)} '
                f'A {r} {r} 0 {la} {sw} {_fmt_f(item.x2)} {_fmt_f(item.y2)}" '
                f'fill="none" '
                f'stroke="{_fmt_color(item.stroke)}" '
                f'stroke-width="{_fmt_f(item.stroke_width)}"/>\n'
            )
        elif isinstance(item, Text):
            if abs(item.rotation_deg) < 1e-9:
                out.append(
                    f'  <text fill="{_fmt_color(item.color)}" '
                    f'font-family="{FONT_FAMILY}" '
                    f'font-size="{_fmt_f(item.font_size)}" '
                    f'text-anchor="{item.anchor.value}" '
                    f'x="{_fmt_f(item.x)}" '
                    f'y="{_fmt_f(item.y)}">{_xml_escape(item.text)}</text>\n'
                )
            else:
                out.append(
                    f'  <text fill="{_fmt_color(item.color)}" '
                    f'font-family="{FONT_FAMILY}" '
                    f'font-size="{_fmt_f(item.font_size)}" '
                    f'text-anchor="{item.anchor.value}" '
                    f'transform="rotate({_fmt_f(item.rotation_deg)} '
                    f'{_fmt_f(item.x)} {_fmt_f(item.y)})" '
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
