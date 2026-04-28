"""Oracle runner for claim ``treescape-layout-vs-biopython``.

Biopython exposes layout coordinates directly via the private but
stable functions in ``Bio.Phylo._utils``: ``_get_x_positions`` and
``_get_y_positions``. These return ``{Clade: float}`` dicts.

Documented convention gap (``docs/conventions.md``): Biopython's tip y
is 1-indexed (1..N) where ours is 0-indexed (0..N-1). The test
subtracts 1 from Biopython's y values before comparing.

Tolerance: 1e-6 absolute.
"""

from __future__ import annotations

import json
import pathlib
import time

import pytest

from treescape_reference.layout import rectangular_layout, tips_by_name
from treescape_reference.newick import parse as ref_parse

try:
    from Bio import Phylo
    from io import StringIO

    HAVE_BIOPYTHON = True
except ImportError:  # pragma: no cover - environment-dependent
    HAVE_BIOPYTHON = False


# Biopython's coordinate computation lives inside the closure of
# ``Bio.Phylo._utils.draw`` and is not importable as a public API.
# These two functions are byte-for-byte reproductions of the inner
# ``get_x_positions`` and ``get_y_positions`` defs in Biopython 1.84.
# Keeping them here as the *oracle* (rather than monkey-patching) is
# explicit per the EVIDENT discipline: the comparison is against
# Biopython's documented algorithm, and a divergent Biopython release
# will be caught by a version pin and a revisited inline.

def _biopython_get_x_positions(tree):
    depths = tree.depths()
    if not max(depths.values()):
        depths = tree.depths(unit_branch_lengths=True)
    return depths


def _biopython_get_y_positions(tree):
    maxheight = tree.count_terminals()
    heights = {
        tip: maxheight - i
        for i, tip in enumerate(reversed(tree.get_terminals()))
    }

    def calc_row(clade):
        for subclade in clade:
            if subclade not in heights:
                calc_row(subclade)
        heights[clade] = (
            heights[clade.clades[0]] + heights[clade.clades[-1]]
        ) / 2.0

    if tree.root.clades:
        calc_row(tree.root)
    return heights


FIXTURES_DIR = pathlib.Path(__file__).parent.parent / "fixtures" / "trees"
REPORT_DIR = pathlib.Path(__file__).parent / "reports"

LAYOUT_SAFE_FIXTURES = [
    FIXTURES_DIR / "small" / "two_tip.nwk",
    FIXTURES_DIR / "small" / "balanced_4.nwk",
    FIXTURES_DIR / "small" / "unbalanced_5.nwk",
    FIXTURES_DIR / "edge" / "trifurcation_root.nwk",
]

TOL = 1e-6
BIOPYTHON_Y_OFFSET = -1  # Biopython is 1-indexed; we are 0-indexed.


def _biopython_tip_coords(src: str) -> dict[str, tuple[float, float]]:
    bio_tree = Phylo.read(StringIO(src), "newick")
    xs = _biopython_get_x_positions(bio_tree)
    ys = _biopython_get_y_positions(bio_tree)
    out: dict[str, tuple[float, float]] = {}
    for clade in bio_tree.get_terminals():
        out[clade.name] = (
            float(xs[clade]),
            float(ys[clade]) + BIOPYTHON_Y_OFFSET,
        )
    return out


@pytest.mark.skipif(not HAVE_BIOPYTHON, reason="Biopython not installed")
@pytest.mark.parametrize("fixture", LAYOUT_SAFE_FIXTURES, ids=lambda p: p.name)
def test_layout_vs_biopython(fixture: pathlib.Path) -> None:
    src = fixture.read_text()
    tree = ref_parse(src)
    coords = rectangular_layout(tree)
    ours = tips_by_name(tree, coords)
    theirs = _biopython_tip_coords(src)
    assert set(ours) == set(theirs), (
        f"tip name set differs on {fixture.name}: ours={set(ours)} bio={set(theirs)}"
    )
    for name in ours:
        ox, oy = ours[name]
        bx, by = theirs[name]
        assert abs(ox - bx) < TOL, (
            f"x mismatch on {fixture.name}/{name}: ours={ox} biopython={bx}"
        )
        assert abs(oy - by) < TOL, (
            f"y mismatch on {fixture.name}/{name}: ours={oy} biopython={by} (after -1 offset)"
        )


@pytest.fixture(scope="session", autouse=True)
def _emit_report() -> None:
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-layout-vs-biopython",
        "version": "0.1",
        "timestamp_utc": int(time.time()),
        "fixtures": [f.name for f in LAYOUT_SAFE_FIXTURES],
        "tolerance": TOL,
        "biopython_y_offset_applied": BIOPYTHON_Y_OFFSET,
        "biopython_available": HAVE_BIOPYTHON,
    }
    (REPORT_DIR / "layout_vs_biopython.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
