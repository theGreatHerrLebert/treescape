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

import html
import re
import shutil
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
BLOB = "https://github.com/theGreatHerrLebert/treescape/blob/main/"
RAW = "https://raw.githubusercontent.com/theGreatHerrLebert/treescape/main/"


def _github_links(text: str, base: str) -> str:
    """Rewrite relative markdown links to GitHub URLs (``base`` is the
    source file's directory relative to the repo root). Images point at
    the raw file, links at the GitHub page; fenced code is left alone."""

    def fix(match: re.Match) -> str:
        bang, label, target = match.group(1), match.group(2), match.group(3)
        if re.match(r"^(https?:|#|mailto:)", target):
            return match.group(0)
        path = (Path(base) / target).as_posix()
        parts = []
        for part in path.split("/"):
            if part == "..":
                parts and parts.pop()
            elif part not in ("", "."):
                parts.append(part)
        return f"{bang}[{label}]({RAW if bang else BLOB}{'/'.join(parts)})"

    link = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]+)\)")
    chunks = re.split(r"(^```.*?^```[^\n]*$)", text, flags=re.M | re.S)
    return "".join(c if c.startswith("```") else link.sub(fix, c) for c in chunks)


def _text(value: object) -> str:
    """One-line claim text, safe inside Markdown and table cells. Outside
    code spans: HTML-escaped (so literal placeholders like ``<fixture>``
    survive) and pipes escaped. Code spans are left alone: they escape
    themselves, Markdown ignores backslashes in them, and the table
    extension does not split cells on a pipe inside backticks."""
    parts = re.split(r"(`[^`]*`)", " ".join(str(value).split()))
    return "".join(
        p if p.startswith("`") else html.escape(p, quote=False).replace("|", "\\|") for p in parts
    )


def _field(claim: dict, key: str) -> str:
    try:
        return str(claim[key])
    except KeyError:
        raise ValueError(f"evident.yaml claim {claim.get('id', '?')!r} has no {key!r}") from None


def _claims_page() -> str:
    manifest = yaml.safe_load((REPO / "evident.yaml").read_text())
    claims = manifest["claims"]
    lines = [
        "# Claims",
        "",
        "Generated from [`evident.yaml`](" + BLOB + "evident.yaml) at build time. Every "
        "claim names its oracle, tolerance, and the command that checks it. `ci` claims run "
        "on every push to `main` and every pull request; `release` claims (R/ggtree) run in "
        "the validation image on a manual run before tagging and again when the `v*` tag is pushed.",
        "",
        f"**{len(claims)} claims.**",
        "",
        "| Claim | Tier | Oracle | Tolerance |",
        "|---|---|---|---|",
    ]
    for c in claims:
        ev = c.get("evidence", {})
        oracle = _text("; ".join(str(o) for o in ev.get("oracle", [])))
        tol = _text(ev.get("tolerance", ""))
        lines.append(
            f"| [{_text(_field(c, 'title'))}](#{_field(c, 'id')}) | `{_field(c, 'tier')}` | {oracle} | {tol} |"
        )
    for c in claims:
        ev = c.get("evidence", {})
        lines += [
            "",
            f"## {_text(_field(c, 'title')).replace('{', '&#123;')} {{ #{_field(c, 'id')} }}",
            "",
            f"`{_field(c, 'id')}` · tier `{_field(c, 'tier')}` · source `{_field(c, 'source')}`",
            "",
            _text(_field(c, "claim")),
            "",
            f"**Check:** `{ev.get('command', '')}`",
        ]
        for heading, key in (("Assumptions", "assumptions"), ("Failure modes", "failure_modes")):
            items = c.get(key) or []
            if items:
                lines += ["", f"**{heading}**", ""] + [f"- {_text(i)}" for i in items]
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
