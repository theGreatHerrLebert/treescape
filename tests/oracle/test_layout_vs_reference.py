"""Oracle runner for claim ``treescape-layout-rust-vs-reference``.

Phase 2 status: this claim compares Rust output to the Python reference.
The Rust path is reachable from Python only after Phase 4 wires the
PyO3 connector. Until then this test is skip-marked with a clear
phase-gate message; the Phase 4 commit will fill in the body.

The reference is exercised by every other layout oracle test in this
directory (vs ete3, vs Biopython, vs ggtree), so a regression in the
reference will be caught upstream of this claim.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Phase 4 deliverable: requires PyO3 connector to expose Rust layout")
def test_rust_layout_matches_reference_within_tolerance() -> None:
    """Rust rectangular_layout coordinates agree with treescape-reference within 1e-9."""
    raise NotImplementedError
