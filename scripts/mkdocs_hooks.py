"""MkDocs build hook for the treescape docs site.

Before each build it:

- copies ``assets/primates.svg`` and ``assets/gallery/`` into
  ``docs/assets/`` (the page images; the committed SVGs stay the single
  source, tested byte-for-byte by tests/oracle/test_gallery_bytes.py);
- copies ``cases/treescape.md`` to ``docs/trust-case.md`` and
  ``packages/Treescape.jl/README.md`` to ``docs/julia.md``, rewriting
  repository-relative links to GitHub URLs;
- generates ``docs/claims.md`` from ``evident.yaml``.

All generated files are gitignored, so the site cannot drift from the
sources it is built from.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
BLOB = "https://github.com/theGreatHerrLebert/treescape/blob/main/"


def _github_links(text: str, base: str) -> str:
    """Rewrite relative markdown links to GitHub URLs (``base`` is the
    source file's directory relative to the repo root)."""

    def fix(match: re.Match) -> str:
        label, target = match.group(1), match.group(2)
        if re.match(r"^(https?:|#|mailto:)", target):
            return match.group(0)
        path = (Path(base) / target).as_posix()
        parts = []
        for part in path.split("/"):
            if part == "..":
                parts and parts.pop()
            elif part not in ("", "."):
                parts.append(part)
        return f"[{label}]({BLOB}{'/'.join(parts)})"

    return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", fix, text)


def _claims_page() -> str:
    manifest = yaml.safe_load((REPO / "evident.yaml").read_text())
    claims = manifest["claims"]
    lines = [
        "# Claims",
        "",
        "Generated from [`evident.yaml`](" + BLOB + "evident.yaml) at build time. Every "
        "claim names its oracle, tolerance, and the command that checks it. `ci` claims run "
        "on every push; `release` claims (R/ggtree) run in the validation image before a tag.",
        "",
        f"**{len(claims)} claims.**",
        "",
        "| Claim | Tier | Oracle | Tolerance |",
        "|---|---|---|---|",
    ]
    for c in claims:
        ev = c.get("evidence", {})
        oracle = "; ".join(str(o) for o in ev.get("oracle", []))
        tol = " ".join(str(ev.get("tolerance", "")).split())
        lines.append(f"| [{c['title']}](#{c['id']}) | `{c['tier']}` | {oracle} | {tol} |")
    for c in claims:
        ev = c.get("evidence", {})
        lines += [
            "",
            f"## {c['title']} {{ #{c['id']} }}",
            "",
            f"`{c['id']}` · tier `{c['tier']}` · source `{c['source']}`",
            "",
            " ".join(str(c["claim"]).split()),
            "",
            f"**Check:** `{ev.get('command', '')}`",
        ]
        for heading, key in (("Assumptions", "assumptions"), ("Failure modes", "failure_modes")):
            items = c.get(key) or []
            if items:
                lines += ["", f"**{heading}**", ""] + [f"- {' '.join(str(i).split())}" for i in items]
    return "\n".join(lines) + "\n"


def on_pre_build(config, **kwargs) -> None:
    assets = DOCS / "assets"
    if assets.exists():
        shutil.rmtree(assets)
    shutil.copytree(REPO / "assets" / "gallery", assets / "gallery", ignore=shutil.ignore_patterns("*.md"))
    shutil.copy(REPO / "assets" / "primates.svg", assets / "primates.svg")

    (DOCS / "trust-case.md").write_text(_github_links((REPO / "cases" / "treescape.md").read_text(), "cases"))
    (DOCS / "julia.md").write_text(
        _github_links((REPO / "packages" / "Treescape.jl" / "README.md").read_text(), "packages/Treescape.jl")
    )
    (DOCS / "claims.md").write_text(_claims_page())
