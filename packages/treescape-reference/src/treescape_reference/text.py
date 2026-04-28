"""Tip-label width measurement reference implementation.

Backs the ``treescape-text-width-vs-fontdue`` EVIDENT claim. The Rust
core in ``treescape-render`` measures tip-label widths via fontdue;
this module is the Python oracle, reading HMTX advance widths
directly from the bundled ``DejaVuSans.ttf`` via ``fontTools``.

Independence: fontTools parses the TTF tables in pure Python; fontdue
has its own pure-Rust parser. They do not share code, but they do
share the underlying TTF file. The claim's tolerance (0.5 px) is set
to absorb fontdue's subpixel rounding in ``metrics().advance_width``.

Scope: Latin only, no shaping (no kerning, no ligatures). v0.2 covers
ASCII + Latin-1 tip names; downstream support follows when a real
fixture surfaces.
"""

from __future__ import annotations

from importlib.resources import files
from functools import lru_cache

from fontTools.ttLib import TTFont


_FONT_RESOURCE = "fonts/DejaVuSans.ttf"


@lru_cache(maxsize=1)
def _font() -> TTFont:
    path = files("treescape_reference").joinpath(_FONT_RESOURCE)
    return TTFont(str(path), lazy=True)


@lru_cache(maxsize=1)
def _cmap() -> dict[int, str]:
    return _font().getBestCmap()


@lru_cache(maxsize=1)
def _hmtx_advances() -> dict[str, int]:
    hmtx = _font()["hmtx"]
    return {name: aw for name, (aw, _lsb) in hmtx.metrics.items()}


@lru_cache(maxsize=1)
def _units_per_em() -> int:
    return _font()["head"].unitsPerEm


def text_width(text: str, font_size: float) -> float:
    """Width in pixels of *text* rendered at *font_size*.

    Sum of HMTX advance widths for each character's mapped glyph,
    scaled by ``font_size / units_per_em``. Empty strings return 0.0.
    Characters absent from the font's cmap fall back to the
    ``.notdef`` glyph advance, matching what an SVG renderer would
    do when drawing an unsupported character.
    """
    if not text:
        return 0.0
    cmap = _cmap()
    hmtx = _hmtx_advances()
    upem = _units_per_em()
    scale = float(font_size) / float(upem)
    notdef = hmtx.get(".notdef", 0)
    total = 0
    for ch in text:
        glyph = cmap.get(ord(ch))
        total += hmtx[glyph] if glyph is not None else notdef
    return total * scale
