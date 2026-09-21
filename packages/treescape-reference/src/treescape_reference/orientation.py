"""Orientation of the rectangular layout (docs/conventions.md, "Orientation").

The ``"right"`` scene is built as always; every other orientation is an
exact transform of it. With the ``"right"`` canvas ``W x H``:

    left   (x, y) -> (W - x, y)      canvas W x H   anchors start <-> end
    down   (x, y) -> (y, x)          canvas H x W   anchors start <-> end, rotation - 90
    up     (x, y) -> (y, W - x)      canvas H x W   anchors unchanged,    rotation - 90

Text is never transposed (that would mirror the glyphs): only its anchor
point moves, and the anchor and rotation keep it readable.
"""

from __future__ import annotations

from typing import Callable, Tuple

from .scene import AnnularSector, Arc, Canvas, Line, Rect, Scene, Text, TextAnchor

ORIENTATIONS = ("right", "down", "left", "up")

_SWAP = {TextAnchor.START: TextAnchor.END, TextAnchor.END: TextAnchor.START, TextAnchor.MIDDLE: TextAnchor.MIDDLE}


def check_orientation(orientation: str) -> str:
    if orientation not in ORIENTATIONS:
        raise ValueError(f"orientation must be one of {ORIENTATIONS}, got {orientation!a}")
    return orientation


def orient_scene(scene: Scene, orientation: str) -> Scene:
    """The ``"right"`` scene transformed to ``orientation``."""
    check_orientation(orientation)
    if orientation == "right":
        return scene
    w, h = scene.canvas.width, scene.canvas.height
    point: Callable[[float, float], Tuple[float, float]]
    if orientation == "left":
        point = lambda x, y: (w - x, y)  # noqa: E731
        canvas = Canvas(w, h)
    elif orientation == "down":
        point = lambda x, y: (y, x)  # noqa: E731
        canvas = Canvas(h, w)
    else:  # up
        point = lambda x, y: (y, w - x)  # noqa: E731
        canvas = Canvas(h, w)
    swap_anchor = orientation in ("left", "down")
    rotate = orientation in ("down", "up")

    items = []
    for item in scene.items:
        if isinstance(item, Rect):
            if orientation == "left":
                items.append(Rect(w - item.x - item.width, item.y, item.width, item.height, item.fill))
            elif orientation == "down":
                items.append(Rect(item.y, item.x, item.height, item.width, item.fill))
            else:
                items.append(Rect(item.y, w - item.x - item.width, item.height, item.width, item.fill))
        elif isinstance(item, Line):
            x1, y1 = point(item.x1, item.y1)
            x2, y2 = point(item.x2, item.y2)
            items.append(Line(x1, y1, x2, y2, item.stroke, item.stroke_width))
        elif isinstance(item, Text):
            x, y = point(item.x, item.y)
            items.append(
                Text(
                    x=x,
                    y=y,
                    text=item.text,
                    font_size=item.font_size,
                    color=item.color,
                    anchor=_SWAP[item.anchor] if swap_anchor else item.anchor,
                    is_tip_label=item.is_tip_label,
                    rotation_deg=item.rotation_deg - 90.0 if rotate else item.rotation_deg,
                )
            )
        elif isinstance(item, (Arc, AnnularSector)):
            raise ValueError("orientation applies to the rectangular layout only")
        else:
            raise TypeError(f"unknown scene item {item!r}")
    return Scene(canvas=canvas, items=items)


__all__ = ["ORIENTATIONS", "check_orientation", "orient_scene"]
