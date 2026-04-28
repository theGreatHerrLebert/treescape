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
import warnings
from pathlib import Path
from typing import Optional, Union

from treescape_connector.py_render import (
    CircularSceneOptions,
    SceneOptions,
    render_circular_svg,
    render_rectangular_styled_svg,
    render_rectangular_svg,
)
from treescape_connector.py_tree import Tree as _RustTree


def _parse_color(spec: Union[str, tuple]) -> tuple:
    """Normalize a user color spec to ``(r, g, b, a)`` 0–255 ints.

    Accepts:
    * ``"#rrggbb"`` or ``"#rrggbbaa"``
    * ``(r, g, b)`` or ``(r, g, b, a)`` tuples (0–255 each)
    """
    if isinstance(spec, str):
        s = spec.lstrip("#")
        if len(s) == 6:
            r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
            return (r, g, b, 255)
        if len(s) == 8:
            r, g, b, a = (
                int(s[0:2], 16),
                int(s[2:4], 16),
                int(s[4:6], 16),
                int(s[6:8], 16),
            )
            return (r, g, b, a)
        raise ValueError(f"hex color must be #rrggbb or #rrggbbaa; got {spec!r}")
    if isinstance(spec, tuple):
        if len(spec) == 3:
            r, g, b = spec
            return (int(r), int(g), int(b), 255)
        if len(spec) == 4:
            r, g, b, a = spec
            return (int(r), int(g), int(b), int(a))
        raise ValueError(f"color tuple must be (r,g,b) or (r,g,b,a); got {spec!r}")
    raise TypeError(f"color must be str or tuple, got {type(spec).__name__}")


_TABLEAU_10 = (
    "#4e79a7",
    "#f28e2b",
    "#e15759",
    "#76b7b2",
    "#59a14f",
    "#edc948",
    "#b07aa1",
    "#ff9da7",
    "#9c755f",
    "#bab0ac",
)


class TreescapeStyleWarning(UserWarning):
    """Warning raised when metadata-driven styling cannot be applied cleanly."""


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
        # v0.2 Phase-3 styling state. Lists/dicts kept order-preserving
        # so the styling-determinism claim holds across runs.
        self._highlights: list[tuple[list[str], tuple[int, int, int, int]]] = []
        self._tip_colors: dict[str, tuple[int, int, int, int]] = {}
        self._scale_bar: Optional[tuple[float, str]] = None
        self._support_labels: bool = False
        self._support_min: Optional[float] = None
        self._metadata_rows: dict[str, dict] = {}
        self._metadata_columns: set[str] = set()
        self._branch_colors: dict[int, tuple[int, int, int, int]] = {}

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

        Shared knobs (``padding``, ``font_size``, ``label_offset``,
        ``stroke_width``) and ``px_per_x`` (which maps to ``px_per_r``
        for circular layouts since both axes carry cumulative branch
        length) are applied to both the rectangular and circular option
        structs. ``px_per_y`` is rectangular-only.

        v0.2 dropped the ``avg_glyph_width`` parameter: tip-label widths
        are measured via fontdue against the bundled DejaVu Sans. See
        ``docs/conventions.md`` for the full convention.
        """
        rect_kwargs = {
            "px_per_x": self._scene_opts.px_per_x,
            "px_per_y": self._scene_opts.px_per_y,
            "padding": self._scene_opts.padding,
            "font_size": self._scene_opts.font_size,
            "label_offset": self._scene_opts.label_offset,
            "stroke_width": self._scene_opts.stroke_width,
        }
        for key, value in (
            ("px_per_x", px_per_x),
            ("px_per_y", px_per_y),
            ("padding", padding),
            ("font_size", font_size),
            ("label_offset", label_offset),
            ("stroke_width", stroke_width),
        ):
            if value is not None:
                rect_kwargs[key] = value
        self._scene_opts = SceneOptions(**rect_kwargs)

        circ_kwargs = {
            "px_per_r": self._circular_opts.px_per_r,
            "padding": self._circular_opts.padding,
            "font_size": self._circular_opts.font_size,
            "label_offset": self._circular_opts.label_offset,
            "stroke_width": self._circular_opts.stroke_width,
            "start_angle": self._circular_opts.start_angle,
            "sweep_total": self._circular_opts.sweep_total,
        }
        for key, value in (
            ("px_per_r", px_per_x),
            ("padding", padding),
            ("font_size", font_size),
            ("label_offset", label_offset),
            ("stroke_width", stroke_width),
        ):
            if value is not None:
                circ_kwargs[key] = value
        self._circular_opts = CircularSceneOptions(**circ_kwargs)
        return self

    def highlight_clade(
        self,
        tips: list,
        color: Union[str, tuple] = "#e07b00",
        alpha: float = 0.3,
    ) -> "TreePlot":
        """Highlight the clade rooted at ``MRCA(tips)`` with a
        translucent rectangle behind the branches.

        v0.2 Phase 3: rectangular layouts only. Calling this with
        ``.layout("circular")`` raises ``NotImplementedError`` at
        :meth:`to_svg`-time.

        ``alpha`` overrides the alpha component of ``color`` if the
        latter is fully opaque. If ``color`` already encodes alpha
        (e.g. ``"#rrggbbaa"`` or 4-tuple), that takes precedence.
        """
        if not tips:
            raise ValueError("highlight_clade requires at least one tip name")
        r, g, b, a = _parse_color(color)
        # If user passed an opaque hex/3-tuple AND a non-default alpha,
        # apply alpha. Otherwise the spec wins.
        if a == 255 and alpha != 1.0:
            a = max(0, min(255, int(round(alpha * 255))))
        self._highlights.append((list(tips), (r, g, b, a)))
        return self

    def color_tips(self, mapping: dict) -> "TreePlot":
        """Override tip-label color per name. ``mapping`` is
        ``{tip_name: color}`` where color is ``"#rrggbb"`` /
        ``"#rrggbbaa"`` or an ``(r,g,b)`` / ``(r,g,b,a)`` tuple.
        Tips not in ``mapping`` keep the default label color."""
        for name, spec in mapping.items():
            self._tip_colors[name] = _parse_color(spec)
        return self

    def join_metadata(self, df, on: str) -> "TreePlot":
        """Join a Polars DataFrame onto tree tips.

        ``on`` names the column whose values match Newick tip names.
        Extra rows, duplicate keys, and metadata-column collisions raise
        ``ValueError``.
        """
        try:
            import polars as pl
        except ImportError as exc:  # pragma: no cover - dependency packaging guard
            raise ImportError("join_metadata requires polars") from exc

        if not isinstance(df, pl.DataFrame):
            raise TypeError("join_metadata expects a polars.DataFrame")
        if on not in df.columns:
            raise ValueError(f"metadata join column {on!r} not found")

        metadata_columns = [c for c in df.columns if c != on]
        collisions = sorted(c for c in metadata_columns if c in self._metadata_columns)
        if collisions:
            raise ValueError(f"metadata column collision(s): {collisions}")

        tip_names = set(self._tree.tip_order())
        keys = df[on].to_list()
        seen = set()
        duplicates = []
        for key in keys:
            if key in seen and key not in duplicates:
                duplicates.append(key)
            seen.add(key)
        if duplicates:
            raise ValueError(f"duplicate metadata key(s): {duplicates}")

        extras = [key for key in keys if key not in tip_names]
        if extras:
            preview = extras[:5]
            raise ValueError(
                f"metadata has {len(extras)} row(s) whose {on!r} value is not a tree tip: {preview}"
            )

        rows = {row[on]: row for row in df.to_dicts()}
        for tip in tip_names:
            current = dict(self._metadata_rows.get(tip, {}))
            source = rows.get(tip)
            for column in metadata_columns:
                current[column] = None if source is None else source[column]
            self._metadata_rows[tip] = current
        self._metadata_columns.update(metadata_columns)
        return self

    def _metadata_for(self, tip_name: str) -> Optional[dict]:
        if not self._metadata_columns:
            return None
        return dict(self._metadata_rows.get(tip_name, {}))

    def color_tips_by(self, column: str, palette: Optional[dict] = None) -> "TreePlot":
        """Color tip labels by a joined categorical metadata column."""
        if column not in self._metadata_columns:
            raise ValueError(f"metadata column {column!r} has not been joined")
        palette = self._resolve_discrete_palette(column, palette)

        mapping = {}
        for tip in self._tree.tip_order():
            value = self._metadata_rows.get(tip, {}).get(column)
            if value is not None:
                mapping[tip] = palette[value]
        return self.color_tips(mapping)

    def color_branches_by(self, column: str, palette: Optional[dict] = None) -> "TreePlot":
        """Color internal branches by monophyletic discrete metadata values.

        A branch is colored when every descendant tip under its child node
        has the same non-missing value for ``column``. Mixed or missing
        values leave the branch at the default color and raise
        ``TreescapeStyleWarning``.
        """
        if column not in self._metadata_columns:
            raise ValueError(f"metadata column {column!r} has not been joined")
        palette = self._resolve_discrete_palette(column, palette)

        root = self._tree.root
        for node_id in self._tree.preorder():
            if node_id == root or self._tree.is_tip(node_id):
                continue
            tips = self._descendant_tips(node_id)
            values = [self._metadata_rows.get(tip, {}).get(column) for tip in tips]
            observed = [value for value in values if value is not None]
            distinct = []
            for value in observed:
                if value not in distinct:
                    distinct.append(value)
            if len(distinct) == 1 and len(observed) == len(tips):
                self._branch_colors[node_id] = _parse_color(palette[distinct[0]])
                continue
            warnings.warn(
                f"branch {self._branch_label(node_id)} is not monophyletic for metadata column "
                f"{column!r}; leaving default branch color",
                TreescapeStyleWarning,
                stacklevel=2,
            )
        return self

    def _resolve_discrete_palette(self, column: str, palette: Optional[dict]) -> dict:
        values = []
        for tip in self._tree.tip_order():
            value = self._metadata_rows.get(tip, {}).get(column)
            if value is not None and value not in values:
                values.append(value)

        if palette is None:
            if len(values) > len(_TABLEAU_10):
                raise ValueError("default categorical palette supports at most 10 values")
            return {value: _TABLEAU_10[i] for i, value in enumerate(values)}

        missing = [value for value in values if value not in palette]
        if missing:
            raise ValueError(f"palette missing value(s) for {column!r}: {missing}")
        return palette

    def _descendant_tips(self, node_id: int) -> list[str]:
        out = []
        stack = [node_id]
        while stack:
            current = stack.pop()
            if self._tree.is_tip(current):
                name = self._tree.name(current)
                if name:
                    out.append(name)
            else:
                stack.extend(reversed(self._tree.children(current)))
        return out

    def _branch_label(self, node_id: int) -> str:
        name = self._tree.name(node_id)
        return name if name else f"node {node_id}"

    def scale_bar(self, length: float, label: Optional[str] = None) -> "TreePlot":
        """Draw a branch-length scale bar below a rectangular tree.

        ``length`` is in the same branch-length units as the Newick edge
        lengths. If ``label`` is omitted, the numeric length is used.
        """
        length = float(length)
        if length <= 0:
            raise ValueError("scale_bar length must be positive")
        self._scale_bar = (length, str(length) if label is None else str(label))
        return self

    def support_labels(self, min_value: Optional[float] = None) -> "TreePlot":
        """Render internal node names as support labels.

        If ``min_value`` is provided, internal node names must parse as
        numbers and meet the threshold to render.
        """
        self._support_labels = True
        self._support_min = None if min_value is None else float(min_value)
        return self

    def to_svg(self) -> str:
        """Render and return the SVG bytes as a UTF-8 string."""
        styled = (
            bool(self._highlights)
            or bool(self._tip_colors)
            or bool(self._branch_colors)
            or self._scale_bar is not None
            or self._support_labels
        )
        if self._layout == "rectangular":
            if styled:
                return render_rectangular_styled_svg(
                    self._tree,
                    self._scene_opts,
                    list(self._highlights),
                    dict(self._tip_colors),
                    self._scale_bar,
                    self._support_labels,
                    self._support_min,
                    list(self._branch_colors.items()),
                )
            return render_rectangular_svg(self._tree, self._scene_opts)
        if self._layout == "circular":
            if styled:
                raise NotImplementedError(
                    "circular layout does not yet support .highlight_clade or "
                    ".color_tips or .color_branches_by or .scale_bar or "
                    ".support_labels; v0.3 will lift this. Drop styling or "
                    "switch to .layout('rectangular')."
                )
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
