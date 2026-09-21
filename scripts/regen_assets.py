"""Regenerate the README screenshot at ``assets/primates.svg`` and the
example gallery at ``assets/gallery/``.

Run from repo root:

    .venv/bin/python scripts/regen_assets.py

Pinned options here are the canonical "marketing render" — change here
if you want the README screenshot to look different. v0.2 widths come
from fontdue against the bundled DejaVu Sans, so dimensions changed
when the 0.6-em monospace approximation was retired (see CHANGELOG).

The gallery covers v0.1 → v0.3 features on a single 12-tip primate
fixture so users can compare options apples-to-apples. Synthetic
metadata (clade taxonomy + bootstrap-style support) is defined inline
here, intentionally — the gallery is documentation, not test data, and
keeping it out of ``tests/fixtures/metadata/`` avoids confusion.
"""

from __future__ import annotations

import pathlib
import warnings
from typing import Callable

import polars as pl

from treescape import TreePlot


REPO = pathlib.Path(__file__).resolve().parent.parent
SOURCE = REPO / "tests" / "fixtures" / "trees" / "medium" / "primates.nwk"
TARGET = REPO / "assets" / "primates.svg"
GALLERY_DIR = REPO / "assets" / "gallery"


PRIMATES_METADATA = pl.DataFrame(
    {
        "tip": [
            "Homo_sapiens",
            "Pan_troglodytes",
            "Gorilla_gorilla",
            "Pongo_abelii",
            "Hylobates_lar",
            "Macaca_mulatta",
            "Papio_anubis",
            "Cercopithecus_mitis",
            "Chlorocebus_sabaeus",
            "Callithrix_jacchus",
            "Saimiri_sciureus",
        ],
        "clade": [
            "great_apes",
            "great_apes",
            "great_apes",
            "great_apes",
            "lesser_apes",
            "old_world_monkeys",
            "old_world_monkeys",
            "old_world_monkeys",
            "old_world_monkeys",
            "new_world_monkeys",
            "new_world_monkeys",
        ],
        "support": [
            0.99,
            0.97,
            0.95,
            0.91,
            0.88,
            0.93,
            0.92,
            0.85,
            0.83,
            0.78,
            0.75,
        ],
    }
)


GREAT_APES = ["Homo_sapiens", "Pan_troglodytes", "Gorilla_gorilla", "Pongo_abelii"]


def _base_rectangular() -> TreePlot:
    """Rectangular primates plot with consistent gallery options."""
    return TreePlot(str(SOURCE)).options(
        padding=16,
        px_per_x=1200,
        px_per_y=24,
        font_size=12,
    )


def _base_circular() -> TreePlot:
    """Circular primates plot with consistent gallery options.

    px_per_x doubles as px_per_r in the circular path; we bump it to
    fill the canvas without labels overlapping the radial branches.
    """
    return TreePlot(str(SOURCE)).layout("circular").options(
        padding=16,
        px_per_x=900,
        font_size=12,
    )


def _marketing() -> TreePlot:
    """Top-level assets/primates.svg — the README screenshot."""
    return TreePlot(str(SOURCE)).options(
        padding=16,
        px_per_x=1500,
        px_per_y=20,
        font_size=12,
    )


def _meta(plot: TreePlot) -> TreePlot:
    return plot.join_metadata(PRIMATES_METADATA, on="tip")


def _branches_by_clade() -> TreePlot:
    # The primates topology has paraphyletic ancestors (e.g., the
    # catarrhine MRCA mixes great_apes + lesser_apes + old_world_monkeys),
    # which emit TreescapeStyleWarning and are left at the default stroke
    # color — visible in the SVG as default branches connecting the
    # colored monophyletic subtrees.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return _meta(_base_rectangular()).color_branches_by("clade")


# (file name, builder). tests/oracle/test_gallery_bytes.py renders each
# builder in memory and asserts the bytes equal the committed file, so
# this list is both the regen recipe and the gallery's regression test.
GALLERY: list[tuple[str, Callable[[], TreePlot]]] = [
    # ---- v0.1 → v0.3 ----
    ("01_rectangular.svg", _base_rectangular),
    ("02_circular.svg", _base_circular),
    (
        "03_rectangular_highlight.svg",
        lambda: _base_rectangular().highlight_clade(GREAT_APES, color="#ffb84d", alpha=0.35),
    ),
    (
        "04_circular_highlight.svg",
        lambda: _base_circular().highlight_clade(GREAT_APES, color="#ffb84d", alpha=0.35),
    ),
    ("05_color_tips_by_clade.svg", lambda: _meta(_base_rectangular()).color_tips_by("clade")),
    ("06_color_branches_by_clade.svg", _branches_by_clade),
    ("07_color_tips_by_support.svg", lambda: _meta(_base_rectangular()).color_tips_by("support")),
    (
        "08_color_branches_by_support.svg",
        lambda: _meta(_base_rectangular()).color_branches_by("support"),
    ),
    # The primates fixture has no internal-node names, so .support_labels
    # would be a no-op here; the scale bar keeps the example self-explanatory.
    (
        "09_scale_bar.svg",
        lambda: _base_rectangular().scale_bar(0.05, "0.05 substitutions/site"),
    ),
    # Highlight + discrete tip color + scale bar: a near-publication render.
    (
        "10_combined.svg",
        lambda: _meta(_base_rectangular())
        .color_tips_by("clade")
        .highlight_clade(GREAT_APES, color="#ffb84d", alpha=0.25)
        .scale_bar(0.05, "0.05 substitutions/site"),
    ),
    # ---- v0.4 ----
    (
        "11_circular_color_tips_by_clade.svg",
        lambda: _meta(_base_circular()).color_tips_by("clade"),
    ),
    ("12_circular_scale_bar.svg", lambda: _base_circular().scale_bar(0.05, "0.05 subs/site")),
    # Numeric support → width via subtree mean on internals, tip value on
    # terminals. Default range (1.0, 4.0) px.
    (
        "13_branch_width_by_support.svg",
        lambda: _meta(_base_rectangular()).width_branches_by("support"),
    ),
]


def main() -> None:
    _marketing().save(str(TARGET))
    print(f"wrote {TARGET.relative_to(REPO)}")
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    print(f"gallery → {GALLERY_DIR.relative_to(REPO)}/")
    for name, build in GALLERY:
        target = GALLERY_DIR / name
        build().save(str(target))
        print(f"  wrote {target.relative_to(REPO)}")


if __name__ == "__main__":
    main()
