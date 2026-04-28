"""Oracle runner for claim ``treescape-text-width-vs-fontdue``.

Tier: ``ci``. Compares the Rust ``text_width`` (fontdue) against the
Python reference ``text_width`` (fontTools HMTX read) on a battery of
representative strings covering ASCII, Latin-1 with accents, narrow
and wide glyphs, embedded spaces, and edge sizes.

Both implementations read the same bundled ``DejaVuSans.ttf`` (the
file is shipped in both ``treescape-render/src/fonts/`` and
``packages/treescape-reference/src/treescape_reference/fonts/`` to
keep the Python package independently installable).

Tolerance is ``0.5`` px absolute per string; in practice both impls
produce floating-point-identical values across these cases.
"""

from __future__ import annotations

import json
import pathlib
import time

import pytest

from treescape_reference.text import text_width as ref_text_width

try:
    from treescape_connector.py_render import text_width as rust_text_width

    HAVE_CONNECTOR = True
except ImportError:  # pragma: no cover
    HAVE_CONNECTOR = False


REPORT_DIR = pathlib.Path(__file__).parent / "reports"
TOL = 0.5


CASES = [
    ("empty", ""),
    ("single_narrow_i", "i"),
    ("single_wide_W", "W"),
    ("ascii_lower", "abcdefghijklmnopqrstuvwxyz"),
    ("ascii_upper", "ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    ("ascii_digits", "0123456789"),
    ("hello_world", "Hello, World!"),
    ("latin1_accents", "café résumé naïve"),
    ("punct_brackets", "[(){}]<>!?.,;:"),
    ("repeated_narrow", "iiiiiiiiii"),
    ("repeated_wide", "WWWWWWWWWW"),
    ("mixed_widths", "iWiWiWiWiW"),
    ("space_runs", "a   b  c d"),
    ("len_64",
        "The quick brown fox jumps over the lazy dog 0123456789 abcdef!"),
]

SIZES = [8.0, 10.0, 12.0, 16.0, 24.0]


@pytest.mark.skipif(
    not HAVE_CONNECTOR,
    reason="treescape_connector not built (run pip install -e ./treescape-connector)",
)
@pytest.mark.parametrize("font_size", SIZES, ids=lambda v: f"{v}px")
@pytest.mark.parametrize("name,text", CASES, ids=[c[0] for c in CASES])
def test_text_width_rust_matches_reference(name: str, text: str, font_size: float) -> None:
    ref = ref_text_width(text, font_size)
    rust = rust_text_width(text, font_size)
    assert abs(rust - ref) < TOL, (
        f"text_width mismatch on {name!r} @ {font_size}px: "
        f"rust={rust} ref={ref} delta={rust - ref}"
    )


@pytest.fixture(scope="session", autouse=True)
def _emit_report() -> None:
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-text-width-vs-fontdue",
        "version": "0.1",
        "timestamp_utc": int(time.time()),
        "n_cases": len(CASES),
        "sizes": SIZES,
        "tolerance": TOL,
        "tier": "ci",
    }
    (REPORT_DIR / "text_width.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
