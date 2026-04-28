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
    import inspect
    import re
    import textwrap

    from Bio import Phylo
    from Bio.Phylo import _utils as _bio_utils
    from io import StringIO

    HAVE_BIOPYTHON = True
except ImportError:  # pragma: no cover - environment-dependent
    HAVE_BIOPYTHON = False


def _extract_biopython_layout_funcs():
    """Pull ``get_x_positions`` and ``get_y_positions`` straight out of
    the installed ``Bio.Phylo._utils.draw`` source.

    These functions are inner closures of ``draw``; they are not
    importable as public API. Rather than copy them inline (which
    would freeze the oracle to the version we typed against and
    silently drift if Biopython updates the algorithm), we read the
    installed source via ``inspect`` and ``exec`` the actual
    definitions. This means the oracle calls *Biopython's own bytes*
    even though the API is private — the strongest practical form of
    the independent-Biopython claim.

    Extraction walks the source by indentation: a line ``    def
    get_*_positions`` opens a block that runs until the next line at
    the same or lesser indent that is not blank. This handles inner
    helper functions like ``calc_row`` correctly.

    Returns ``(get_x_positions, get_y_positions, biopython_version)``.
    Raises ``RuntimeError`` if extraction fails, which surfaces as a
    test failure rather than a silent skip.
    """
    raw = inspect.getsource(_bio_utils.draw)
    src = textwrap.dedent(raw)
    lines = src.splitlines(keepends=True)

    def _block_at(start_idx: int) -> str:
        opener = lines[start_idx]
        opener_indent = len(opener) - len(opener.lstrip())
        chunk = [opener]
        for line in lines[start_idx + 1 :]:
            if not line.strip():
                chunk.append(line)
                continue
            indent = len(line) - len(line.lstrip())
            if indent <= opener_indent:
                break
            chunk.append(line)
        return "".join(chunk)

    blocks: dict = {}
    for idx, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("def get_x_positions(") or stripped.startswith(
            "def get_y_positions("
        ):
            name = stripped.split("(", 1)[0].split()[-1]
            blocks[name] = textwrap.dedent(_block_at(idx))

    if "get_x_positions" not in blocks or "get_y_positions" not in blocks:
        raise RuntimeError(
            "could not extract get_x_positions/get_y_positions from "
            f"Bio.Phylo._utils.draw source (found {sorted(blocks)})"
        )

    namespace: dict = {}
    for src_chunk in blocks.values():
        exec(src_chunk, namespace)

    import Bio  # noqa: WPS433
    return (
        namespace["get_x_positions"],
        namespace["get_y_positions"],
        getattr(Bio, "__version__", "unknown"),
    )


if HAVE_BIOPYTHON:
    (
        _biopython_get_x_positions,
        _biopython_get_y_positions,
        _BIOPYTHON_VERSION,
    ) = _extract_biopython_layout_funcs()
else:
    _BIOPYTHON_VERSION = "unavailable"


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
        "biopython_version": _BIOPYTHON_VERSION,
        "extraction_method": "inspect.getsource on Bio.Phylo._utils.draw",
    }
    (REPORT_DIR / "layout_vs_biopython.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
