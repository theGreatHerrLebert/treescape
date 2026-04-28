"""User-facing declarative grammar for treescape.

v0.1 surface area is intentionally tight: load a Newick tree, choose
the rectangular layout, render tip labels, save SVG. Color/metadata
joins, circular and radial layouts, clade highlighting, and
branch/node styling all land in v0.2 and are documented in plan.md.

Example:

    from treescape import TreePlot

    TreePlot("tree.nwk").save("tree.svg")

    TreePlot(
        "((a:1,b:1):1,(c:1,d:1):1);"
    ).layout("rectangular").save("/tmp/tree.svg")
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union

from treescape_connector.py_render import (
    CircularSceneOptions,
    SceneOptions,
    render_circular_svg,
    render_rectangular_svg,
)
from treescape_connector.py_tree import Tree as _RustTree


class TreePlot:
    """Declarative phylogenetic tree plot.

    Args:
        source: A path to a Newick file or an inline Newick string. The
            heuristic for deciding which: if ``source`` contains a
            newline, ends with ``;`` after stripping, or doesn't exist
            as a file, it's treated as inline text.

    Methods chain — each returns ``self``.
    """

    _SUPPORTED_LAYOUTS = ("rectangular", "circular")

    def __init__(self, source: Union[str, Path]) -> None:
        self._tree = _load_tree(source)
        self._layout: str = "rectangular"
        self._scene_opts = SceneOptions()
        self._circular_opts = CircularSceneOptions()

    def layout(self, kind: str) -> "TreePlot":
        if kind not in self._SUPPORTED_LAYOUTS:
            raise ValueError(
                f"supported layouts: {self._SUPPORTED_LAYOUTS}; got {kind!r}. "
                "Radial / unrooted layouts are a v0.3 deliverable."
            )
        self._layout = kind
        return self

    def tips(self, label: str = "name") -> "TreePlot":
        """Configure tip labels.

        ``label="name"`` uses the tip's own name from the Newick file.
        Other label sources (e.g. ``label="species"`` from a metadata
        join) require the metadata API which is a v0.2 deliverable.
        """
        if label != "name":
            raise NotImplementedError(
                f"label={label!r} requires metadata join (v0.2). "
                "v0.1 supports only label='name'."
            )
        return self

    def options(
        self,
        px_per_x: Optional[float] = None,
        px_per_y: Optional[float] = None,
        padding: Optional[float] = None,
        font_size: Optional[float] = None,
        label_offset: Optional[float] = None,
        stroke_width: Optional[float] = None,
    ) -> "TreePlot":
        """Override scene-build options. Any value left as ``None`` keeps
        the current default.

        v0.2 dropped the ``avg_glyph_width`` parameter: tip-label widths
        are measured via fontdue against the bundled DejaVu Sans. See
        ``docs/conventions.md`` for the full convention.
        """
        defaults = {
            "px_per_x": self._scene_opts.px_per_x,
            "px_per_y": self._scene_opts.px_per_y,
            "padding": self._scene_opts.padding,
            "font_size": self._scene_opts.font_size,
            "label_offset": 4.0,
            "stroke_width": 1.0,
        }
        kwargs = dict(defaults)
        for key, value in (
            ("px_per_x", px_per_x),
            ("px_per_y", px_per_y),
            ("padding", padding),
            ("font_size", font_size),
            ("label_offset", label_offset),
            ("stroke_width", stroke_width),
        ):
            if value is not None:
                kwargs[key] = value
        self._scene_opts = SceneOptions(**kwargs)
        return self

    def to_svg(self) -> str:
        """Render and return the SVG bytes as a UTF-8 string."""
        if self._layout == "rectangular":
            return render_rectangular_svg(self._tree, self._scene_opts)
        if self._layout == "circular":
            return render_circular_svg(self._tree, self._circular_opts)
        raise AssertionError(f"unreachable: layout {self._layout!r}")

    def save(self, path: Union[str, Path]) -> "TreePlot":
        """Render and write SVG to ``path``."""
        Path(path).write_text(self.to_svg())
        return self

    def __repr__(self) -> str:
        return (
            f"TreePlot(n_tips={self._tree.n_tips()}, "
            f"layout={self._layout!r})"
        )


def _load_tree(source: Union[str, Path]) -> _RustTree:
    """Resolve ``source`` to a Newick string and parse via the Rust core."""
    if isinstance(source, Path):
        return _RustTree.parse_newick(source.read_text())
    if isinstance(source, str):
        stripped = source.strip()
        looks_like_newick = (
            "\n" in source
            or stripped.endswith(";")
            or stripped.startswith("(")
        )
        if not looks_like_newick:
            # Treat as a file path
            return _RustTree.parse_newick(Path(source).read_text())
        if os.path.exists(source) and not stripped.startswith("("):
            # ambiguous — file path that also looks like newick? prefer file.
            return _RustTree.parse_newick(Path(source).read_text())
        return _RustTree.parse_newick(source)
    raise TypeError(
        f"TreePlot source must be a path or Newick string, got {type(source).__name__}"
    )
