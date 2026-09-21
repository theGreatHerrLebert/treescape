"""Oracle runner for claim ``treescape-layout-vs-biopython``.

Biopython computes layout coordinates in ``get_x_positions`` /
``get_y_positions``, inner functions of ``Bio.Phylo._utils.draw``. The
runner executes Biopython's own source for them (see
``_extract_biopython_layout_funcs``), so the oracle is Biopython's code,
not a copy of it.

Compared, for both treescape implementations (Rust core,
``treescape-reference``) on the ``layout-v2`` corpus, nodes matched by
clade (``_layouts.py``):

* x of every node;
* y of every tip, after Biopython's 1-based offset (``y - 1``);
* y of every internal node whose whole subtree is binary. At a
  multifurcation Biopython uses the midpoint of the first and last child
  and treescape the mean of all children (``docs/conventions.md``), and
  the difference propagates to every ancestor, whose y is the mean of its
  children's. That documented gap is excluded, not tolerated.

Tolerance: 1e-6 absolute.
"""

from __future__ import annotations

import inspect
import json
import textwrap
import time
from io import StringIO

import pytest

from _julia import REPO
from _layouts import CASE_IDS, CASES, LAYOUT_CORPUS, binary_subtrees, label, rectangular

Phylo = pytest.importorskip("Bio.Phylo", reason="Biopython not installed")
from Bio.Phylo import _utils as _bio_utils  # noqa: E402

REPORT_DIR = REPO / "tests" / "oracle" / "reports"
TOL = 1e-6
BIOPYTHON_Y_OFFSET = -1  # Biopython is 1-indexed; we are 0-indexed.


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


(
    _biopython_get_x_positions,
    _biopython_get_y_positions,
    _BIOPYTHON_VERSION,
) = _extract_biopython_layout_funcs()


def biopython_nodes(src: str) -> dict[frozenset, tuple[float, float]]:
    bio_tree = Phylo.read(StringIO(src), "newick")
    xs = _biopython_get_x_positions(bio_tree)
    ys = _biopython_get_y_positions(bio_tree)
    clades = list(bio_tree.find_clades())
    out = {
        frozenset(t.name for t in clade.get_terminals()): (float(xs[clade]), float(ys[clade]) + BIOPYTHON_Y_OFFSET)
        for clade in clades
    }
    assert len(out) == len(clades), "Biopython clades do not identify nodes"
    return out


@pytest.mark.parametrize("fixture,impl", CASES, ids=CASE_IDS)
def test_layout_vs_biopython(fixture, impl) -> None:
    src = fixture.read_text()
    ours, theirs, binary = rectangular(src, impl), biopython_nodes(src), binary_subtrees(src)
    assert set(ours) == set(theirs), f"clade sets differ on {fixture.name}"
    for clade, (bx, by) in theirs.items():
        ox, oy = ours[clade]
        assert abs(ox - bx) < TOL, f"x mismatch on {fixture.name}/{label(clade)} ({impl}): ours={ox} biopython={bx}"
        if clade in binary:
            assert abs(oy - by) < TOL, (
                f"y mismatch on {fixture.name}/{label(clade)} ({impl}): ours={oy} biopython={by} (after -1 offset)"
            )


@pytest.fixture(scope="session", autouse=True)
def _emit_report():
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-layout-vs-biopython",
        "version": "0.6",
        "timestamp_utc": int(time.time()),
        "corpus": "layout-v2",
        "fixtures": [f"{f.parent.name}/{f.name}" for f in LAYOUT_CORPUS],
        "implementations": ["reference", "rust"],
        "compared": "x of every node; y of every node whose subtree is binary (tips included)",
        "tolerance": TOL,
        "biopython_y_offset_applied": BIOPYTHON_Y_OFFSET,
        "biopython_version": _BIOPYTHON_VERSION,
    }
    (REPORT_DIR / "layout_vs_biopython.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
