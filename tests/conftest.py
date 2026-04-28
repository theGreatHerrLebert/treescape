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
