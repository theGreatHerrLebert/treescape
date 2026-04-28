"""Reference metadata join semantics for :class:`treescape.TreePlot`.

The v0.3 metadata API is deliberately Python-side only. This module is
the readable convention owner used by oracle tests: it validates a
Polars frame against a tree's tip universe and returns plain Python row
dicts keyed by tip name.
"""

from __future__ import annotations

from typing import Dict, Iterable, Optional

import polars as pl


MetadataRows = Dict[str, Dict[str, object]]


def join_metadata(
    tip_names: Iterable[str],
    df: pl.DataFrame,
    *,
    on: str,
    existing_rows: Optional[MetadataRows] = None,
    existing_columns: Optional[set[str]] = None,
) -> tuple[MetadataRows, set[str]]:
    """Join metadata rows onto ``tip_names``.

    The join key column is not stored as metadata. Returned rows include
    all tips in the tree; missing tips get ``None`` for each incoming
    metadata column.
    """
    if not isinstance(df, pl.DataFrame):
        raise TypeError("join_metadata expects a polars.DataFrame")
    if on not in df.columns:
        raise ValueError(f"metadata join column {on!r} not found")

    tips = set(tip_names)
    metadata_columns = [c for c in df.columns if c != on]
    prior_columns = set() if existing_columns is None else set(existing_columns)
    collisions = sorted(c for c in metadata_columns if c in prior_columns)
    if collisions:
        raise ValueError(f"metadata column collision(s): {collisions}")

    keys = df[on].to_list()
    seen = set()
    duplicates = []
    for key in keys:
        if key in seen and key not in duplicates:
            duplicates.append(key)
        seen.add(key)
    if duplicates:
        raise ValueError(f"duplicate metadata key(s): {duplicates}")

    extras = [key for key in keys if key not in tips]
    if extras:
        raise ValueError(
            f"metadata has {len(extras)} row(s) whose {on!r} value is not a tree tip: {extras[:5]}"
        )

    source_rows = {row[on]: row for row in df.to_dicts()}
    out: MetadataRows = {
        tip: dict(existing_rows.get(tip, {})) if existing_rows else {} for tip in tips
    }
    for tip in tips:
        source = source_rows.get(tip)
        for column in metadata_columns:
            out[tip][column] = None if source is None else source[column]

    return out, prior_columns | set(metadata_columns)


__all__ = ["MetadataRows", "join_metadata"]
