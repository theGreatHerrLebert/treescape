"""Shared R/ggtree oracle access for the release-tier layout runners.

``workflow/scripts/oracle_ggtree.R`` prints one CSV row per node
(``node, parent, x|r, y|theta, is_tip, label``). Rows are keyed here by
clade (``_layouts.clades_from_parents``), so they match treescape nodes
regardless of ggtree's node numbering. Results are cached per tree and
layout: both treescape implementations are compared with one R run.
"""

from __future__ import annotations

import csv
import functools
import io
import shutil
import subprocess

from _julia import REPO
from _layouts import clades_from_parents

SCRIPT = REPO / "workflow" / "scripts" / "oracle_ggtree.R"


@functools.cache
def available() -> bool:
    if shutil.which("Rscript") is None:
        return False
    probe = subprocess.run(
        ["Rscript", "-e", 'cat(requireNamespace("ggtree", quietly = TRUE))'],
        capture_output=True, text=True, check=False,
    )
    return probe.returncode == 0 and probe.stdout.strip() == "TRUE"


@functools.cache
def nodes(fixture: str, circular: bool = False) -> dict[frozenset, dict]:
    """``{clade: row}`` for every node of ``fixture`` (a path string)."""
    args = ["Rscript", str(SCRIPT), fixture] + (["--circular"] if circular else [])
    out = subprocess.run(args, capture_output=True, text=True, check=True).stdout
    rows = list(csv.DictReader(io.StringIO(out)))
    clades = clades_from_parents(rows)
    return {clades[row["node"]]: row for row in rows}
