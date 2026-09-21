"""Docs examples runner (evidence for claim ``treescape-julia-python-svg-parity``).

Executes every example on the docs pages in ``PAGES`` (``docs/examples.md``,
``docs/matlab.md``) in both languages. Each
example is marked ``<!-- example: FILE.svg -->`` and must leave a plot in
``p`` whose SVG equals ``assets/gallery/FILE.svg`` byte for byte — the
image the page shows under it. The page's ``<!-- setup -->`` blocks run
first. Code in other languages (the MATLAB column) is shown, not run.

Blocks run in a scratch directory (examples call ``save``) that links
``tests/`` from the repository, so the relative fixture paths resolve.
Julia blocks run in one Julia process; they skip (or fail under
``TREESCAPE_REQUIRE_JULIA=1``) when Julia or the connector is missing.
"""

from __future__ import annotations

import os
import re
import subprocess
import textwrap
from pathlib import Path

import pytest

from _julia import JL_PACKAGE, REPO, jl_library, julia_executable, require

PAGES = [REPO / "docs" / "examples.md", REPO / "docs" / "matlab.md"]
GALLERY = REPO / "assets" / "gallery"

_MARKER = re.compile(r"<!--\s*(setup|example:\s*(\S+))\s*-->")
_FENCE = re.compile(r"^( *)```(python|julia)\n(.*?)^\1```", re.S | re.M)
_IMAGE = re.compile(r"!\[[^\]]*\]\(assets/gallery/([^)\s]+)\)")


def _sections(doc: Path) -> list[tuple[str | None, dict[str, str], str | None]]:
    """``[(expected file or None for setup, {"python": code, "julia": code}, first gallery image)]``."""
    text = doc.read_text()
    marks = list(_MARKER.finditer(text))
    sections = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        found = _FENCE.findall(text[m.end():end])
        langs = [lang for _, lang, _ in found]
        # A second block in one language would silently replace the first.
        assert len(langs) == len(set(langs)), f"{doc.name}: duplicate language block after {m.group(0)}"
        blocks = {lang: textwrap.dedent(code) for _, lang, code in found}
        image = _IMAGE.search(text, m.end(), end)
        sections.append((m.group(2), blocks, image.group(1) if image else None))
    return sections


def _loose_fences(doc: Path) -> int:
    """Every python/julia fence on the page, however it is written (tabs,
    info strings, CRLF): each must be one the parser above picked up."""
    return len(re.findall(r"^[ \t]*```\s*(?:python|julia)\b", doc.read_text(), re.M))


SECTIONS = {doc: _sections(doc) for doc in PAGES}
SETUP = {doc: [blocks for name, blocks, _ in secs if name is None] for doc, secs in SECTIONS.items()}
EXAMPLES = [(doc, name, blocks) for doc, secs in SECTIONS.items() for name, blocks, _ in secs if name is not None]
EXAMPLE_IDS = [f"{doc.stem}/{name}" for doc, name, _ in EXAMPLES]


@pytest.mark.parametrize("doc", PAGES, ids=[d.name for d in PAGES])
def test_every_example_has_both_languages_and_an_image(doc):
    assert SETUP[doc] and any(d == doc for d, _, _ in EXAMPLES)
    for name, blocks, image in SECTIONS[doc]:
        assert set(blocks) == {"python", "julia"}, name or "setup"
        if name is not None:
            assert (GALLERY / name).is_file(), name
            assert image == name, f"the image shown under {name} is {image}"


@pytest.mark.parametrize("doc", PAGES, ids=[d.name for d in PAGES])
def test_no_code_block_is_skipped(doc):
    """Fences before the first marker, or written so the parser misses
    them, would otherwise never run."""
    parsed = sum(len(blocks) for _, blocks, _ in SECTIONS[doc])
    assert parsed == _loose_fences(doc), f"{_loose_fences(doc) - parsed} python/julia block(s) are not executed"


@pytest.fixture()
def scratch(tmp_path, monkeypatch):
    (tmp_path / "tests").symlink_to(REPO / "tests")
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.parametrize("doc,name,blocks", EXAMPLES, ids=EXAMPLE_IDS)
def test_python_example_reproduces_its_image(doc, name, blocks, scratch):
    pytest.importorskip("polars", reason="polars required for the examples")
    pytest.importorskip("treescape_connector.py_render", reason="treescape_connector not built")
    ns: dict = {}
    for setup in SETUP[doc]:
        exec(setup["python"], ns)
    exec(blocks["python"], ns)
    assert ns["p"].to_svg() == (GALLERY / name).read_text()


JULIA_DRIVER = r'''
# Runs each docs example in a fresh module after the setup code and
# writes the resulting plot's SVG to <outdir>/<name>.
setup, outdir = ARGS[1], ARGS[2]
for (name, file) in zip(ARGS[3:2:end], ARGS[4:2:end])
    m = Module()
    Core.eval(m, :(using Treescape))
    Base.include(m, setup)
    Base.include(m, file)
    write(joinpath(outdir, name), Core.eval(m, :(Treescape.to_svg(p))))
    println("OK ", name)
end
'''


@pytest.mark.parametrize("doc", PAGES, ids=[d.name for d in PAGES])
def test_julia_examples_reproduce_their_images(doc, scratch):
    julia, lib = julia_executable(), jl_library()
    require(julia, lib)
    (scratch / "setup.jl").write_text("\n".join(b["julia"] for b in SETUP[doc]))
    (scratch / "driver.jl").write_text(JULIA_DRIVER)
    examples = [(name, blocks) for d, name, blocks in EXAMPLES if d == doc]
    args = []
    for name, blocks in examples:
        path = scratch / f"{name}.jl"
        path.write_text(blocks["julia"])
        args += [name, str(path)]
    outdir = scratch / "out"
    outdir.mkdir()
    env = dict(os.environ, TREESCAPE_JL_LIB=str(lib))
    proc = subprocess.run(
        [julia, f"--project={JL_PACKAGE}", str(scratch / "driver.jl"), str(scratch / "setup.jl"), str(outdir), *args],
        cwd=scratch, env=env, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr[-4000:]
    for name, _ in examples:
        assert (outdir / name).read_text() == (GALLERY / name).read_text(), f"Julia example {doc.name}/{name} differs"
