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

import polars as pl

from treescape import TreePlot


REPO = pathlib.Path(__file__).resolve().parent.parent
SOURCE = REPO / "tests" / "fixtures" / "trees" / "medium" / "primates.nwk"
TARGET = REPO / "assets" / "primates.svg"
GALLERY = REPO / "assets" / "gallery"


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


def _save(plot: TreePlot, name: str) -> pathlib.Path:
    target = GALLERY / name
    plot.save(str(target))
    print(f"  wrote {target.relative_to(REPO)}")
    return target


def _render_marketing() -> None:
    """Top-level assets/primates.svg — the README screenshot."""
    plot = TreePlot(str(SOURCE)).options(
        padding=16,
        px_per_x=1500,
        px_per_y=20,
        font_size=12,
    )
    plot.save(str(TARGET))
    print(f"wrote {TARGET.relative_to(REPO)}")


def _render_gallery() -> None:
    GALLERY.mkdir(parents=True, exist_ok=True)
    print(f"gallery → {GALLERY.relative_to(REPO)}/")

    # 01 — plain rectangular (v0.1 baseline)
    _save(_base_rectangular(), "01_rectangular.svg")

    # 02 — plain circular (v0.2)
    _save(_base_circular(), "02_circular.svg")

    # 03 — rectangular + clade highlight (v0.2 styling)
    _save(
        _base_rectangular().highlight_clade(GREAT_APES, color="#ffb84d", alpha=0.35),
        "03_rectangular_highlight.svg",
    )

    # 04 — circular + annular-sector highlight (v0.3 Phase 3)
    _save(
        _base_circular().highlight_clade(GREAT_APES, color="#ffb84d", alpha=0.35),
        "04_circular_highlight.svg",
    )

    # 05 — discrete tip color via Tableau-10 (v0.3 Phase 2 discrete)
    _save(
        _base_rectangular().join_metadata(PRIMATES_METADATA, on="tip").color_tips_by("clade"),
        "05_color_tips_by_clade.svg",
    )

    # 06 — discrete branch color via monophyly (v0.3 Phase 2). The
    # primates topology has paraphyletic ancestors (e.g., the catarrhine
    # MRCA mixes great_apes + lesser_apes + old_world_monkeys), which
    # emit TreescapeStyleWarning and are left at the default stroke
    # color — visible in the SVG as default branches connecting the
    # colored monophyletic subtrees.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _save(
            _base_rectangular()
            .join_metadata(PRIMATES_METADATA, on="tip")
            .color_branches_by("clade"),
            "06_color_branches_by_clade.svg",
        )

    # 07 — continuous tip color via viridis (v0.3 Phase 2 continuous)
    _save(
        _base_rectangular().join_metadata(PRIMATES_METADATA, on="tip").color_tips_by("support"),
        "07_color_tips_by_support.svg",
    )

    # 08 — continuous branch color via viridis (subtree mean)
    _save(
        _base_rectangular()
        .join_metadata(PRIMATES_METADATA, on="tip")
        .color_branches_by("support"),
        "08_color_branches_by_support.svg",
    )

    # 09 — scale bar (v0.3 bonus). The primates fixture has no
    # internal-node names, so .support_labels would be a no-op here;
    # we focus on the scale bar to keep the example self-explanatory.
    _save(
        _base_rectangular().scale_bar(0.05, "0.05 substitutions/site"),
        "09_scale_bar.svg",
    )

    # 10 — combined: highlight + discrete tip color + scale bar.
    # A near-publication-style render of what v0.3 can express.
    _save(
        _base_rectangular()
        .join_metadata(PRIMATES_METADATA, on="tip")
        .color_tips_by("clade")
        .highlight_clade(GREAT_APES, color="#ffb84d", alpha=0.25)
        .scale_bar(0.05, "0.05 substitutions/site"),
        "10_combined.svg",
    )


def main() -> None:
    _render_marketing()
    _render_gallery()


if __name__ == "__main__":
    main()
