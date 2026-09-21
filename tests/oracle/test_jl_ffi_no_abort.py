"""Oracle runner for claim ``treescape-jl-ffi-no-abort``.

Runs ``packages/Treescape.jl/test/ffi_no_abort.jl`` in one Julia
subprocess. The connector aborts on panic (release profile), so a panic
shows up here as a dead process; the failure names the last ``CASE``
line the runner printed. The subprocess runs under an address-space cap
so an unbounded allocation fails fast instead of exhausting the host.

Skips (with the reason) when Julia or the C-ABI library is missing, or
fails instead when ``TREESCAPE_REQUIRE_JULIA=1``.
"""

from __future__ import annotations

import json
import os
import resource
import subprocess
import time
from pathlib import Path

import pytest

from _julia import JL_PACKAGE, REPORT_DIR, jl_library, julia_executable, require

MEMORY_CAP_BYTES = 8 * 1024**3


def _cap_memory() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_CAP_BYTES, MEMORY_CAP_BYTES))


def test_ffi_hostile_inputs_never_abort_julia():
    julia = julia_executable()
    lib = jl_library()
    require(julia, lib)
    env = dict(os.environ, TREESCAPE_JL_LIB=str(lib))
    subprocess.run(
        [julia, f"--project={JL_PACKAGE}", "-e", "using Pkg; Pkg.instantiate()"],
        check=True, env=env, capture_output=True,
    )
    start = time.time()
    proc = subprocess.run(
        [julia, f"--project={JL_PACKAGE}", str(JL_PACKAGE / "test" / "ffi_no_abort.jl")],
        env=env, capture_output=True, text=True, timeout=1800, preexec_fn=_cap_memory,
    )
    lines = proc.stdout.splitlines()
    cases = [l[5:] for l in lines if l.startswith("CASE ")]
    fails = [l[5:] for l in lines if l.startswith("FAIL ")]
    done = next((l for l in reversed(lines) if l.startswith("DONE ")), None)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "jl_ffi_no_abort.json").write_text(json.dumps({
        "claim": "treescape-jl-ffi-no-abort",
        "version": "0.5",
        "timestamp_utc": int(time.time()),
        "tier": "ci",
        "exit_code": proc.returncode,
        "cases_started": len(cases),
        "failures": fails,
        "seconds": round(time.time() - start, 1),
    }, indent=2, sort_keys=True))

    assert done is not None and proc.returncode == 0, (
        f"Julia process died (exit {proc.returncode}) during case {cases[-1] if cases else '?'!r}\n"
        f"stderr:\n{proc.stderr[-4000:]}"
    )
    assert not fails, "\n".join(fails)
    assert done == f"DONE {len(cases)} 0"
