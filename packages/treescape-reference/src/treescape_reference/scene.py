"""Scene graph types — companion to the Rust ``treescape_core::layout::scene``
module. Kept readable rather than fast.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple


@dataclass(frozen=True)
class Color:
    r: int
    g: int
    b: int
    a: int = 255


BLACK = Color(0, 0, 0, 255)


@dataclass(frozen=True)
class Canvas:
    width: float
    height: float


class TextAnchor(Enum):
    START = "start"
    MIDDLE = "middle"
    END = "end"


@dataclass(frozen=True)
class Rect:
    """Filled rectangle. Emitted before Line/Arc/Text so highlights
    render behind branches and labels."""

    x: float
    y: float
    width: float
    height: float
    fill: Color


@dataclass(frozen=True)
class Line:
    x1: float
    y1: float
    x2: float
    y2: float
    stroke: Color = BLACK
    stroke_width: float = 1.0


@dataclass(frozen=True)
class Arc:
    """Circular arc from (x1, y1) to (x2, y2) along a circle of the
    given radius. ``large_arc`` and ``sweep_clockwise`` map onto SVG
    path arc flags. Used by circular layouts for the spine that
    connects an internal node's children."""

    x1: float
    y1: float
    x2: float
    y2: float
    radius: float
    large_arc: bool = False
    sweep_clockwise: bool = True
    stroke: Color = BLACK
    stroke_width: float = 1.0


@dataclass(frozen=True)
class Text:
    x: float
    y: float
    text: str
    font_size: float
    color: Color = BLACK
    anchor: TextAnchor = TextAnchor.START
    is_tip_label: bool = False
    # Rotation in degrees around (x, y); 0.0 = upright. Used to keep
    # circular tip labels radial.
    rotation_deg: float = 0.0


SceneItem = object  # union: Line | Arc | Text


@dataclass
class Scene:
    canvas: Canvas
    items: List[SceneItem] = field(default_factory=list)

    def count_tip_labels(self) -> int:
        return sum(1 for i in self.items if isinstance(i, Text) and i.is_tip_label)

    def coords_within_canvas(self, eps: float = 1e-6) -> bool:
        w, h = self.canvas.width + eps, self.canvas.height + eps
        for item in self.items:
            if isinstance(item, Rect):
                if item.x < -eps or item.x + item.width > w:
                    return False
                if item.y < -eps or item.y + item.height > h:
                    return False
            elif isinstance(item, (Line, Arc)):
                for c in (item.x1, item.x2):
                    if c < -eps or c > w:
                        return False
                for c in (item.y1, item.y2):
                    if c < -eps or c > h:
                        return False
            elif isinstance(item, Text):
                if item.x < -eps or item.x > w or item.y < -eps or item.y > h:
                    return False
        return True


__all__ = [
    "Color",
    "BLACK",
    "Canvas",
    "TextAnchor",
    "Rect",
    "Line",
    "Arc",
    "Text",
    "Scene",
]
