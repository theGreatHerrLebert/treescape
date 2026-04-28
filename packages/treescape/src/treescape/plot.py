"""TreePlot grammar. Implementation lands in Phase 4."""

from __future__ import annotations


class TreePlot:
    def __init__(self, tree):
        self._tree = tree

    def save(self, path):  # pragma: no cover - phase 4
        raise NotImplementedError("TreePlot is a phase-4 deliverable")
