"""Regenerate the README screenshot at assets/primates.svg.

Run from repo root:

    .venv/bin/python scripts/regen_assets.py

Pinned options here are the canonical "marketing render" — change here
if you want the README screenshot to look different. v0.2 widths come
from fontdue against the bundled DejaVu Sans, so dimensions changed
when the 0.6-em monospace approximation was retired (see CHANGELOG).
"""

from __future__ import annotations

import pathlib

from treescape import TreePlot


REPO = pathlib.Path(__file__).resolve().parent.parent
SOURCE = REPO / "tests" / "fixtures" / "trees" / "medium" / "primates.nwk"
TARGET = REPO / "assets" / "primates.svg"


def main() -> None:
    plot = (
        TreePlot(str(SOURCE))
        .options(
            padding=16,
            px_per_x=1500,
            px_per_y=20,
            font_size=12,
        )
    )
    plot.save(str(TARGET))
    print(f"wrote {TARGET}")


if __name__ == "__main__":
    main()
