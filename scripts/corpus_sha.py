"""Content hash of a named input corpus (``evident.yaml`` ``inputs.corpus_sha``).

    python scripts/corpus_sha.py layout-core-4     # prints sha256:<hex>
    python scripts/corpus_sha.py --all             # every corpus

The hash is sha256 over ``path + "\\n" + sha256(file bytes) + "\\n"`` for
each file of the corpus in sorted path order (``docs/conventions.md``,
"EVIDENT manifest"). Corpora are defined in ``tests/fixtures/corpora.toml``.
"""

from __future__ import annotations

import hashlib
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CORPORA = REPO / "tests" / "fixtures" / "corpora.toml"


def corpora() -> dict[str, list[str]]:
    spec = tomllib.loads(CORPORA.read_text())
    return {name: entry["files"] for name, entry in spec["corpora"].items()}


def corpus_sha(files: list[str]) -> str:
    outer = hashlib.sha256()
    for path in sorted(files):
        inner = hashlib.sha256((REPO / path).read_bytes()).hexdigest()
        outer.update(f"{path}\n{inner}\n".encode())
    return "sha256:" + outer.hexdigest()


def main(argv: list[str]) -> int:
    known = corpora()
    names = sorted(known) if argv == ["--all"] else argv
    if not names:
        print(__doc__.strip())
        return 2
    for name in names:
        if name not in known:
            print(f"unknown corpus {name!r}; known: {', '.join(sorted(known))}", file=sys.stderr)
            return 1
        print(f"{name}\t{corpus_sha(known[name])}" if len(names) > 1 else corpus_sha(known[name]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
