"""Shared pytest config: make the in-tree Python packages importable
without requiring `pip install -e` for every developer touching tests.
"""

from __future__ import annotations

import pathlib
import sys

_ROOT = pathlib.Path(__file__).parent.parent
_SRC_PATHS = [
    _ROOT / "packages" / "treescape-reference" / "src",
    _ROOT / "packages" / "treescape" / "src",
]

for p in _SRC_PATHS:
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)


def pytest_collection_modifyitems(config, items):
    """Timing claims (``@pytest.mark.bench``) need a quiet machine: they run
    only when the marker expression names them (``-m bench``), never as part
    of an ordinary or ``-m "not release_only"`` run."""
    if "bench" in (config.getoption("markexpr") or ""):
        return
    kept, dropped = [], []
    for item in items:
        (dropped if item.get_closest_marker("bench") else kept).append(item)
    if dropped:
        config.hook.pytest_deselected(items=dropped)
        items[:] = kept
