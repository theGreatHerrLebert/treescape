"""Docs examples runner (evidence for claim ``treescape-julia-python-svg-parity``).

Executes every example on ``docs/examples.md`` in both languages. Each
example is marked ``<!-- example: FILE.svg -->`` and must leave a plot in
``p`` whose SVG equals ``assets/gallery/FILE.svg`` byte for byte — the
image the page shows under it. The ``<!-- setup -->`` blocks run first.

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

DOC = REPO / "docs" / "examples.md"
GALLERY = REPO / "assets" / "gallery"

_MARKER = re.compile(r"<!--\s*(setup|example:\s*(\S+))\s*-->")
_FENCE = re.compile(r"^( *)```(python|julia)\n(.*?)^\1```", re.S | re.M)


def _sections() -> list[tuple[str | None, dict[str, str]]]:
    """``[(expected file or None for setup, {"python": code, "julia": code})]``."""
    text = DOC.read_text()
    marks = list(_MARKER.finditer(text))
    sections = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        blocks = {lang: textwrap.dedent(code) for _, lang, code in _FENCE.findall(text[m.end():end])}
        sections.append((m.group(2), blocks))
    return sections


SECTIONS = _sections()
SETUP = [blocks for name, blocks in SECTIONS if name is None]
EXAMPLES = [(name, blocks) for name, blocks in SECTIONS if name is not None]


def test_every_example_has_both_languages_and_an_image():
    assert SETUP and EXAMPLES
    for name, blocks in EXAMPLES:
        assert set(blocks) == {"python", "julia"}, name
        assert (GALLERY / name).is_file(), name
        assert f"assets/gallery/{name}" in DOC.read_text(), f"{name} is not shown on the page"


@pytest.fixture()
def scratch(tmp_path, monkeypatch):
    (tmp_path / "tests").symlink_to(REPO / "tests")
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.parametrize("name,blocks", EXAMPLES, ids=[n for n, _ in EXAMPLES])
def test_python_example_reproduces_its_image(name, blocks, scratch):
    pytest.importorskip("polars", reason="polars required for the examples")
    pytest.importorskip("treescape_connector.py_render", reason="treescape_connector not built")
    ns: dict = {}
    for setup in SETUP:
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


def test_julia_examples_reproduce_their_images(scratch):
    julia, lib = julia_executable(), jl_library()
    require(julia, lib)
    (scratch / "setup.jl").write_text("\n".join(b["julia"] for b in SETUP))
    (scratch / "driver.jl").write_text(JULIA_DRIVER)
    args = []
    for name, blocks in EXAMPLES:
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
    for name, _ in EXAMPLES:
        assert (outdir / name).read_text() == (GALLERY / name).read_text(), f"Julia example {name} differs"
