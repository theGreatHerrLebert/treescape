"""Oracle runner for claim ``treescape-layout-vs-ggtree``.

Tier: ``release``. Skipped when R or the ggtree Bioconductor package is
not available. The release Docker image at
``workflow/Dockerfile.evident-release`` (Phase 5 deliverable) ships
both, and CI gates this claim before any release tag.

The R script at ``workflow/scripts/oracle_ggtree.R`` runs ``ggtree`` on
a fixture and emits coordinates as CSV. We compare against the Python
reference's tip coordinates within ``1e-4`` absolute. The tolerance is
looser than ete3/Biopython to absorb ggplot's internal scaling drift.

Convention notes (see ``docs/conventions.md``):

* The R script invokes ``ggtree(tree, ladderize = FALSE)``. ggtree's
  default ``ladderize = TRUE`` reorders children by clade size, which
  ``treescape.rectangular_layout`` does not do implicitly. Disabling it
  makes the comparison like-for-like.
* ggtree's tip y is 1-based (``1..N``). treescape's is 0-based
  (``0..N-1``). The test adds 1 to our y before comparing — same offset
  pattern the Biopython oracle uses.
"""

from __future__ import annotations

import csv
import io
import json
import pathlib
import shutil
import subprocess
import time

import pytest

from treescape_reference.layout import rectangular_layout, tips_by_name
from treescape_reference.newick import parse as ref_parse


WORKSPACE = pathlib.Path(__file__).parent.parent.parent
FIXTURES_DIR = WORKSPACE / "tests" / "fixtures" / "trees"
SCRIPT = WORKSPACE / "workflow" / "scripts" / "oracle_ggtree.R"
REPORT_DIR = pathlib.Path(__file__).parent / "reports"

LAYOUT_SAFE_FIXTURES = [
    FIXTURES_DIR / "small" / "two_tip.nwk",
    FIXTURES_DIR / "small" / "balanced_4.nwk",
    FIXTURES_DIR / "small" / "unbalanced_5.nwk",
    FIXTURES_DIR / "edge" / "trifurcation_root.nwk",
]

TOL = 1e-4


def _has_rscript() -> bool:
    return shutil.which("Rscript") is not None


def _has_ggtree() -> bool:
    if not _has_rscript():
        return False
    probe = subprocess.run(
        [
            "Rscript",
            "-e",
            'cat(requireNamespace("ggtree", quietly = TRUE))',
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return probe.returncode == 0 and probe.stdout.strip() == "TRUE"


def _ggtree_tip_coords(fixture: pathlib.Path) -> dict[str, tuple[float, float]]:
    result = subprocess.run(
        ["Rscript", str(SCRIPT), str(fixture)],
        capture_output=True,
        text=True,
        check=True,
    )
    reader = csv.DictReader(io.StringIO(result.stdout))
    out: dict[str, tuple[float, float]] = {}
    for row in reader:
        if row["is_tip"].upper() != "TRUE":
            continue
        out[row["label"]] = (float(row["x"]), float(row["y"]))
    return out


@pytest.mark.release_only
@pytest.mark.skipif(not _has_ggtree(), reason="R + Bioconductor + ggtree required (release tier)")
@pytest.mark.parametrize("fixture", LAYOUT_SAFE_FIXTURES, ids=lambda p: p.name)
def test_layout_vs_ggtree(fixture: pathlib.Path) -> None:
    src = fixture.read_text()
    tree = ref_parse(src)
    coords = rectangular_layout(tree)
    ours = tips_by_name(tree, coords)
    theirs = _ggtree_tip_coords(fixture)
    assert set(ours) == set(theirs), (
        f"tip name set differs on {fixture.name}: ours={set(ours)} ggtree={set(theirs)}"
    )
    for name in ours:
        ox, oy = ours[name]
        gx, gy = theirs[name]
        assert abs(ox - gx) < TOL, (
            f"x mismatch on {fixture.name}/{name}: ours={ox} ggtree={gx}"
        )
        # ggtree y is 1-based; ours is 0-based. See docs/conventions.md.
        assert abs((oy + 1.0) - gy) < TOL, (
            f"y mismatch on {fixture.name}/{name}: ours+1={oy + 1.0} ggtree={gy}"
        )


@pytest.fixture(scope="session", autouse=True)
def _emit_report() -> None:
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-layout-vs-ggtree",
        "version": "0.1",
        "timestamp_utc": int(time.time()),
        "fixtures": [f.name for f in LAYOUT_SAFE_FIXTURES],
        "tolerance": TOL,
        "rscript_available": _has_rscript(),
        "ggtree_available": _has_ggtree(),
        "tier": "release",
    }
    (REPORT_DIR / "layout_vs_ggtree.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
