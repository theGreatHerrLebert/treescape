"""Oracle runner for claim ``treescape-julia-python-svg-parity``.

Interprets ``tests/fixtures/parity/cases.toml`` with the Python package,
runs ``packages/Treescape.jl/test/parity_runner.jl`` once over the same
file, and requires byte-identical SVG per case. Cases with
``expect_file`` must also equal that committed SVG on both sides.

Skips (with the reason) when Julia or the C-ABI library is missing, or
fails instead when ``TREESCAPE_REQUIRE_JULIA=1``. ``TREESCAPE_JULIA``
overrides the Julia executable (default ``julia`` on PATH).
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import tomllib
import warnings
from pathlib import Path

import pytest

if os.environ.get("TREESCAPE_REQUIRE_JULIA") == "1":
    # Required mode (CI julia job): a missing Python prerequisite must fail
    # the run, not skip the whole module.
    import polars as pl
    import treescape_connector.py_render  # noqa: F401
else:
    pl = pytest.importorskip("polars", reason="polars required for metadata cases")
    pytest.importorskip(
        "treescape_connector.py_render",
        reason="treescape_connector not built (run pip install -e ./treescape-connector)",
    )

from _julia import JL_PACKAGE, REPO, REPORT_DIR, jl_library, julia_executable, require  # noqa: E402
from treescape import TreePlot  # noqa: E402

CASES_PATH = REPO / "tests" / "fixtures" / "parity" / "cases.toml"
SPEC = tomllib.loads(CASES_PATH.read_text())
CASE_NAMES = [c["name"] for c in SPEC["cases"]]


def test_cases_file_has_no_ignored_tables() -> None:
    """A misspelled table (``[[case]]``) would silently drop its cases."""
    assert set(SPEC) <= {"trees", "tables", "cases"}, sorted(set(SPEC) - {"trees", "tables", "cases"})
    assert len(CASE_NAMES) == len(set(CASE_NAMES)), "duplicate case names"


# --- Python driver ------------------------------------------------------------


def _tuplify(value):
    if isinstance(value, list) and all(isinstance(v, (int, float)) for v in value):
        return tuple(value)
    return value


def _python_svg(case: dict) -> str:
    source = SPEC["trees"][case["tree"]]
    src = str(REPO / source["path"]) if "path" in source else source["newick"]
    plot = TreePlot(src)
    for step in case["ops"]:
        op = step["op"]
        args = list(step.get("args", []))
        kwargs = dict(step.get("kwargs", {}))
        if op == "join_metadata":
            args[0] = pl.DataFrame(SPEC["tables"][args[0]])
        if op == "color_tips":
            args[0] = {k: _tuplify(v) for k, v in args[0].items()}
        if "color" in kwargs:
            kwargs["color"] = _tuplify(kwargs["color"])
        if "palette" in kwargs:
            kwargs["palette"] = {k: _tuplify(v) for k, v in kwargs["palette"].items()}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            getattr(plot, op)(*args, **kwargs)
    return plot.to_svg()


# --- Julia driver -------------------------------------------------------------


@pytest.fixture(scope="module")
def julia_outputs(tmp_path_factory) -> Path:
    julia = julia_executable()
    lib = jl_library()
    require(julia, lib)
    outdir = tmp_path_factory.mktemp("julia_parity")
    env = dict(os.environ, TREESCAPE_JL_LIB=str(lib))
    subprocess.run(
        [julia, f"--project={JL_PACKAGE}", "-e", "using Pkg; Pkg.instantiate()"],
        check=True,
        env=env,
        capture_output=True,
    )
    proc = subprocess.run(
        [julia, f"--project={JL_PACKAGE}", str(JL_PACKAGE / "test" / "parity_runner.jl"),
         str(CASES_PATH), str(REPO), str(outdir)],
        env=env,
        capture_output=True,
        text=True,
    )
    last = proc.stdout.strip().splitlines()[-1:] or [""]
    assert proc.returncode == 0 and last[0] == f"DONE {len(CASE_NAMES)}", (
        f"Julia parity runner failed (exit {proc.returncode}); last line {last[0]!r}\n"
        f"stderr:\n{proc.stderr[-4000:]}"
    )
    return outdir


_RESULTS: dict[str, bool] = {}


@pytest.mark.parametrize("name", CASE_NAMES)
def test_julia_matches_python(name, julia_outputs):
    case = next(c for c in SPEC["cases"] if c["name"] == name)
    python_svg = _python_svg(case)
    julia_svg = (julia_outputs / f"{name}.svg").read_text()
    _RESULTS[name] = julia_svg == python_svg
    assert julia_svg == python_svg, f"{name}: Julia and Python SVG differ"
    if "expect_file" in case:
        committed = (REPO / case["expect_file"]).read_text()
        assert python_svg == committed, f"{name}: differs from {case['expect_file']}"


def test_cases_cover_every_gallery_file():
    expected = {f"assets/gallery/{p.name}" for p in (REPO / "assets" / "gallery").glob("*.svg")}
    expected.add("assets/primates.svg")
    assert expected == {c["expect_file"] for c in SPEC["cases"] if "expect_file" in c}


@pytest.fixture(scope="session", autouse=True)
def _emit_report():
    yield
    if not _RESULTS:
        return
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-julia-python-svg-parity",
        "version": "0.5",
        "timestamp_utc": int(time.time()),
        "tier": "ci",
        "julia": julia_executable(),
        "cases": len(CASE_NAMES),
        "byte_identical": sum(_RESULTS.values()),
        "mismatched": sorted(n for n, ok in _RESULTS.items() if not ok),
    }
    (REPORT_DIR / "julia_parity.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
