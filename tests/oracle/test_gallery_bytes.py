"""Gallery regression runner (evidence for claim
``treescape-style-resolution-rust-vs-reference``).

Renders every ``scripts/regen_assets.py`` configuration in memory and
asserts the bytes equal the committed files under ``assets/`` — without
overwriting them. A behavior-preserving refactor must leave all of them
byte-identical; an intentional change regenerates them with
``python scripts/regen_assets.py`` and shows up in the diff.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("polars", reason="polars required for gallery metadata")
pytest.importorskip(
    "treescape_connector.py_render",
    reason="treescape_connector not built (run pip install -e ./treescape-connector)",
)

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("regen_assets", REPO / "scripts" / "regen_assets.py")
regen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(regen)


def test_marketing_render_matches_committed_bytes():
    assert regen._marketing().to_svg() == regen.TARGET.read_text()


@pytest.mark.parametrize("name,build", regen.GALLERY, ids=[n for n, _ in regen.GALLERY])
def test_gallery_render_matches_committed_bytes(name, build):
    committed = (regen.GALLERY_DIR / name).read_text()
    assert build().to_svg() == committed, (
        f"assets/gallery/{name} differs from a fresh render; "
        "run `python scripts/regen_assets.py` if the change is intentional"
    )


def test_every_committed_gallery_file_is_covered():
    committed = sorted(p.name for p in regen.GALLERY_DIR.glob("*.svg"))
    assert committed == sorted(n for n, _ in regen.GALLERY)
