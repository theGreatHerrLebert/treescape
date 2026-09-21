# Contributing to treescape

Thanks for your interest. treescape is built on three load-bearing principles. Please read them before opening a PR.

## 1. Oracles before code

Every numerical or structural claim in `evident.yaml` must point to an oracle, a tolerance, a reproducible command, and an artifact path **before** the code that backs it lands. The discipline is intentional — see `cases/treescape.md`.

If you're adding a feature with a new claim:
1. Add the claim to `evident.yaml` with an oracle, tolerance, command, and assumptions.
2. Run `python evident/workflow/validate_manifest.py --strict-release-pins evident.yaml` and `pytest tests/oracle/test_manifest.py` (pins, corpus hashes).
3. Then implement.

If you're fixing a bug, the existing claim runner should fail, then pass after your fix. If it doesn't fail before your fix, the claim is either wrong or the test fixture set is too narrow — that's a separate PR.

## 2. Reference Python first, then Rust

Layout, ladderize, scene construction, and SVG rendering live in **two** places:

- `packages/treescape-reference/src/treescape_reference/` — slow, readable Python. The canonical convention owner.
- `treescape-core/`, `treescape-render/` — fast Rust. Held to match the reference within tolerance.

When you change layout/render behavior, change the Python first. The Rust port follows. The `treescape-layout-rust-vs-reference` claim catches drift; the `treescape-svg-determinism` claim's Rust↔reference byte-equality test catches anything subtler.

## 3. Disagreement is documented, not absorbed

When an external oracle (ete3, Biopython, ggtree) disagrees with us on a fixture, the fix is to write down *why* in `docs/conventions.md`, not to bump tolerance until the test passes. Look at the existing entries (Biopython y-offset, ete3 ladderize tie-break) for the format.

## Setup

```bash
git clone https://github.com/theGreatHerrLebert/treescape.git
cd treescape
git submodule update --init   # `evident` (manifest validator); not --recursive, see ci.yml
python3.12 -m venv .venv
source .venv/bin/activate
pip install maturin
(cd treescape-connector && maturin develop --release)
pip install -e packages/treescape-reference -e packages/treescape
pip install -e "packages/treescape[test]" -r tests/requirements-oracles.txt   # oracle versions pinned to evident.yaml
pip install -r docs/requirements.txt                  # only for the docs site
```

Julia claims need Julia ≥ 1.10 and the C-ABI library: `cargo build -p treescape-jl-connector --release`, then point `TREESCAPE_JULIA` at the Julia binary if it is not on `PATH`.

## Running checks

```bash
cargo test --workspace                       # Rust unit tests
python evident/workflow/validate_manifest.py --strict-release-pins evident.yaml  # Manifest schema (upstream EVIDENT)
pytest tests/oracle -v -m "not release_only"  # All ci-tier oracle claims
mkdocs build --strict                         # Docs site, incl. generated claims page
```

For the release-tier ggtree claims (rectangular and circular), the same command CI runs:

```bash
docker build -f workflow/Dockerfile.evident-release -t treescape-release .
docker run --rm -v "$PWD:/workspace" -w /workspace treescape-release \
    bash -lc "(cd treescape-connector && maturin develop --release) && \
              pip install -e packages/treescape-reference -e packages/treescape && \
              pytest tests/oracle -v -m release_only"
```

Release-tier claims must pass before a release tag is pushed: run the `ci` workflow manually on `main` (Actions → ci → Run workflow), which includes the release tier.

## Adding a fixture

Fixtures live at `tests/fixtures/trees/` and are referenced by ID from claim runners. Every fixture must have a row in `tests/fixtures/trees/FIXTURES.md` recording its source, license, and what edge case it exercises. **Never edit a fixture in place** — claims may have golden artifacts pinned against the exact bytes; add a new fixture instead.

## Code style

- Rust: `cargo fmt`, `cargo clippy --workspace -- -D warnings`. Allow advisory clippy for now; we'll harden once the lint debt is paid down.
- Python: PEP 8, 88-char lines (Black-compatible), type hints on public APIs.

## What goes where

- `treescape-core` — tree model, parsers, traversal, layout, scene graph. No rendering.
- `treescape-render` — SVG emitter, themes. No tree manipulation.
- `treescape-connector` — PyO3 thin layer. No business logic; only forward calls.
- `packages/treescape` — user-facing TreePlot grammar.
- `packages/treescape-reference` — readable Python reference; the EVIDENT oracle for layout and rendering. Keep it slow and obviously correct, **not** fast.

## Asking questions

Open an issue with the `question` label. For design discussions, prefer GitHub Discussions over PR comments.

## Releasing

The steps are in `docs/conventions.md` ("Distribution", "Order of a release"). In short: bump every version; run the `release` workflow (stage `julia-libs`, publish ticked) and commit the `Artifacts.toml` and `ARTIFACTS_SOURCE` it produces; run stage `build-and-test`; run the `ci` workflow manually for the release tier; then push the `v<version>` tag and approve the `pypi` environment. The tag run refuses a version mismatch or Rust sources changed since the artifacts were built.
