"""Shared discovery for the Julia claim runners (no third-party imports,
so a missing optional dependency in one runner cannot skip the other)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
JL_PACKAGE = REPO / "packages" / "Treescape.jl"
REPORT_DIR = Path(__file__).parent / "reports"


def julia_executable() -> str | None:
    """``TREESCAPE_JULIA`` or ``julia`` on PATH."""
    exe = os.environ.get("TREESCAPE_JULIA", "julia")
    return shutil.which(exe) or (exe if Path(exe).is_file() else None)


def jl_library() -> Path | None:
    """``TREESCAPE_JL_LIB`` or the development build under target/release."""
    if "TREESCAPE_JL_LIB" in os.environ:
        path = Path(os.environ["TREESCAPE_JL_LIB"])
        return path if path.is_file() else None
    for name in ("libtreescape_jl_connector.so", "libtreescape_jl_connector.dylib"):
        path = REPO / "target" / "release" / name
        if path.is_file():
            return path
    return None


def require(julia: str | None, lib: Path | None) -> None:
    """Skip with the reason when a prerequisite is missing, or fail when
    ``TREESCAPE_REQUIRE_JULIA=1`` (the CI julia job sets it, so the
    Julia claims cannot pass there by skipping)."""
    missing = []
    if julia is None:
        missing.append("julia not found (set TREESCAPE_JULIA or put julia on PATH)")
    if lib is None:
        missing.append("treescape-jl-connector not built (cargo build -p treescape-jl-connector --release)")
    if not missing:
        return
    if os.environ.get("TREESCAPE_REQUIRE_JULIA") == "1":
        pytest.fail("; ".join(missing))
    pytest.skip("; ".join(missing))
