"""Release-tier tool gate.

A release-tier runner whose tool (R, ggtree, ape, phangorn) is missing
skips with its reason in an ordinary checkout, but **fails** where
``TREESCAPE_REQUIRE_RELEASE=1`` is set — the release image sets it — so a
broken image cannot turn the release tier green by skipping everything.
"""

from __future__ import annotations

import os

import pytest


def require(available: bool, what: str) -> None:
    if available:
        return
    if os.environ.get("TREESCAPE_REQUIRE_RELEASE") == "1":
        pytest.fail(f"{what} is not available but TREESCAPE_REQUIRE_RELEASE=1 (release tier)")
    pytest.skip(f"{what} required (release tier)")
