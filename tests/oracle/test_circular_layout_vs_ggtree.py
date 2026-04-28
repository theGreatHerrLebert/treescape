"""Oracle runner for claim ``treescape-circular-layout-vs-ggtree``.

Tier: ``release``. Skipped when R or the ggtree Bioconductor package
is not available. The release Docker image at
``workflow/Dockerfile.evident-release`` ships both, and CI gates this
claim before any release tag.

The R script at ``workflow/scripts/oracle_ggtree.R --circular`` runs
``ggtree(tree, layout="circular", ladderize=FALSE)`` and emits
``(node, r, θ, is_tip, label)`` as CSV with θ in radians. We compare
against the Python reference's tip ``(r, θ)`` within ``1e-3``
absolute, after the convention transforms documented in
``docs/conventions.md``:

* **Tip placement formula:** treescape's tip *i* (0-based pre-order)
  is at ``π/2 − i·2π/N``. ggtree's tip *i* (1-based pre-order) is at
  ``i·2π/N`` — the LAST tip lands at ``2π = 0`` (3 o'clock), and the
  sweep is CCW. Solving for the comparison: per-tip
  ``θ_ggtree = 2π/N + π/2 − θ_ours`` (mod 2π). For N=4 this collapses
  to ``π − θ_ours`` because ``2π/4 + π/2 = π``; that special case is
  the simplest illustration of the divergence but the general
  formula is what the test applies.
* **Internal-node angle:** ggtree uses the linear mean of children's
  angles; treescape uses the wrap-aware vector mean. Diverges only
  for diametrically-opposed children. The oracle test compares tips
  only to sidestep this — internal-node convention is verified by
  the rust↔reference parity claim instead.
* **Default ladderize:** ggtree() defaults ``ladderize=TRUE``;
  treescape does not ladderize implicitly. Oracle disables via
  ``ladderize=FALSE`` (same as rectangular).
"""

from __future__ import annotations

import csv
import io
import json
import math
import pathlib
import shutil
import subprocess
import time

import pytest

from treescape_reference.layout import circular_layout, tips_by_name
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

TOL = 1e-3


def _has_rscript() -> bool:
    return shutil.which("Rscript") is not None


def _has_ggtree() -> bool:
    if not _has_rscript():
        return False
    probe = subprocess.run(
        ["Rscript", "-e", 'cat(requireNamespace("ggtree", quietly = TRUE))'],
        capture_output=True,
        text=True,
        check=False,
    )
    return probe.returncode == 0 and probe.stdout.strip() == "TRUE"


def _ggtree_tip_polar(fixture: pathlib.Path) -> dict[str, tuple[float, float]]:
    result = subprocess.run(
        ["Rscript", str(SCRIPT), str(fixture), "--circular"],
        capture_output=True,
        text=True,
        check=True,
    )
    reader = csv.DictReader(io.StringIO(result.stdout))
    out: dict[str, tuple[float, float]] = {}
    for row in reader:
        if row["is_tip"].upper() != "TRUE":
            continue
        out[row["label"]] = (float(row["r"]), float(row["theta"]))
    return out


def _angle_diff(a: float, b: float) -> float:
    """Smallest absolute angular difference in radians, treating
    angles as points on the unit circle (so 2π and 0 are the same)."""
    d = (a - b) % (2.0 * math.pi)
    if d > math.pi:
        d = 2.0 * math.pi - d
    return abs(d)


@pytest.mark.release_only
@pytest.mark.skipif(not _has_ggtree(), reason="R + Bioconductor + ggtree required (release tier)")
@pytest.mark.parametrize("fixture", LAYOUT_SAFE_FIXTURES, ids=lambda p: p.name)
def test_circular_layout_vs_ggtree(fixture: pathlib.Path) -> None:
    src = fixture.read_text()
    tree = ref_parse(src)
    coords = circular_layout(tree)
    ours = tips_by_name(tree, coords)
    theirs = _ggtree_tip_polar(fixture)
    assert set(ours) == set(theirs), (
        f"tip name set differs on {fixture.name}: ours={set(ours)} ggtree={set(theirs)}"
    )
    n_tips = len(ours)
    # See module docstring for derivation.
    offset = 2.0 * math.pi / n_tips + math.pi / 2.0
    for name in ours:
        orad, oth = ours[name]
        grad, gth = theirs[name]
        assert abs(orad - grad) < TOL, (
            f"r mismatch on {fixture.name}/{name}: ours={orad} ggtree={grad}"
        )
        expected_gth = offset - oth
        d = _angle_diff(expected_gth, gth)
        assert d < TOL, (
            f"θ mismatch on {fixture.name}/{name}: "
            f"ours={oth} expected_ggtree={expected_gth} got={gth} delta={d}"
        )


@pytest.fixture(scope="session", autouse=True)
def _emit_report() -> None:
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-circular-layout-vs-ggtree",
        "version": "0.1",
        "timestamp_utc": int(time.time()),
        "fixtures": [f.name for f in LAYOUT_SAFE_FIXTURES],
        "tolerance": TOL,
        "rscript_available": _has_rscript(),
        "ggtree_available": _has_ggtree(),
        "tier": "release",
    }
    (REPORT_DIR / "circular_layout_vs_ggtree.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
