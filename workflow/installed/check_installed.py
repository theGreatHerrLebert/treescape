"""Installed-package check (claim treescape-installed-packages-reproduce-gallery).

    python workflow/installed/check_installed.py <repo root> <report.json>

Run from a directory OUTSIDE the repository, in a virtual environment into
which only the built wheels were installed. Asserts that ``treescape`` and
``treescape_connector`` are imported from the environment (never from the
repository's ``packages/`` sources), that the connector wheel carries both
license files, and that every gallery and README SVG
(``scripts/regen_assets.py``) is reproduced byte for byte.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import platform
import sys
from pathlib import Path


def main(repo: Path, report: Path) -> int:
    import treescape
    import treescape_connector
    import treescape_reference

    for module in (treescape, treescape_connector, treescape_reference):
        where = Path(module.__file__).resolve()
        assert repo.resolve() not in where.parents, f"{module.__name__} imported from the repository ({where})"

    files = {Path(f).name for f in importlib.metadata.files("treescape_connector") or []}
    missing = {"LICENSE", "LICENSE.DejaVu.txt"} - files
    assert not missing, f"connector wheel lacks {sorted(missing)}"
    font = Path(treescape_reference.__file__).parent / "fonts" / "DejaVuSans.ttf"
    assert font.is_file(), f"treescape-reference wheel lacks its font ({font})"

    spec = importlib.util.spec_from_file_location("regen_assets", repo / "scripts" / "regen_assets.py")
    regen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(regen)
    results = {}
    for name, build in regen.GALLERY:
        results[name] = build().to_svg() == (regen.GALLERY_DIR / name).read_text(encoding="utf-8")
    results["primates.svg"] = regen._marketing().to_svg() == regen.TARGET.read_text(encoding="utf-8")

    summary = {
        "claim": "treescape-installed-packages-reproduce-gallery",
        "platform": f"{platform.system()}-{platform.machine()}",
        "python": platform.python_version(),
        "treescape": importlib.metadata.version("treescape"),
        "treescape_connector": importlib.metadata.version("treescape-connector"),
        "files": results,
        "mismatches": sorted(k for k, ok in results.items() if not ok),
    }
    report.write_text(json.dumps(summary, indent=2, sort_keys=True))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if summary["mismatches"] else 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]), Path(sys.argv[2])))
