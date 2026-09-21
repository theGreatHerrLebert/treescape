"""Oracle runner for claim ``treescape-layout-rust-vs-reference``.

Compares the Rust layouts (via ``treescape_connector``) with the Python
reference (``treescape_reference``) on every node of every tree in the
``layout-v2`` corpus: rectangular ``(x, y)`` and circular ``(r, θ)``,
within 1e-9 absolute. Nodes are matched by clade (``_layouts.py``).

The Python reference is the canonical convention owner. This claim shows
the Rust port has not drifted from it; correctness comes from the
external-oracle claims, which check both implementations.
"""

from __future__ import annotations

import json
import time

import pytest

from _julia import REPO
from _layouts import LAYOUT_CORPUS, angle_diff, circular, label, rectangular

REPORT_DIR = REPO / "tests" / "oracle" / "reports"
TOL = 1e-9
IDS = [f"{f.parent.name}/{f.name}" for f in LAYOUT_CORPUS]


@pytest.mark.parametrize("fixture", LAYOUT_CORPUS, ids=IDS)
def test_rust_layout_matches_reference(fixture) -> None:
    src = fixture.read_text()
    rust, ref = rectangular(src, "rust"), rectangular(src, "reference")
    assert set(rust) == set(ref), f"clade sets differ on {fixture.name}"
    for clade, (rx, ry) in rust.items():
        ex, ey = ref[clade]
        assert abs(rx - ex) < TOL, f"x drift on {fixture.name}/{label(clade)}: rust={rx} ref={ex}"
        assert abs(ry - ey) < TOL, f"y drift on {fixture.name}/{label(clade)}: rust={ry} ref={ey}"


@pytest.mark.parametrize("fixture", LAYOUT_CORPUS, ids=IDS)
def test_rust_circular_layout_matches_reference(fixture) -> None:
    src = fixture.read_text()
    rust, ref = circular(src, "rust"), circular(src, "reference")
    assert set(rust) == set(ref), f"clade sets differ on {fixture.name}"
    for clade, (rr, rt) in rust.items():
        er, et = ref[clade]
        assert abs(rr - er) < TOL, f"r drift on {fixture.name}/{label(clade)}: rust={rr} ref={er}"
        assert angle_diff(rt, et) < TOL, f"θ drift on {fixture.name}/{label(clade)}: rust={rt} ref={et}"


@pytest.fixture(scope="session", autouse=True)
def _emit_report():
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-layout-rust-vs-reference",
        "version": "0.6",
        "timestamp_utc": int(time.time()),
        "corpus": "layout-v2",
        "fixtures": IDS,
        "compared": "every node, rectangular (x, y) and circular (r, θ)",
        "tolerance": TOL,
    }
    (REPORT_DIR / "layout_rust_vs_reference.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
