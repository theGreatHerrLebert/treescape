# NEXT — pick up here

Working notes for resuming v0.1.0 ship work. Delete or merge into CHANGELOG once tagged.

## Where we are

Phase 5 polish: **substantially done, not tagged yet**. All review items from the last two rounds closed.

```
phases:  0✓ 1✓ 2✓ 3✓ 4✓ 5≈
tests:   30 core + 7 render Rust unit; 64 pytest pass + 4 release_only deselected
manifest: validate_manifest.py green; eight claims pinned
clippy:   cargo clippy --workspace -- -D warnings clean
ci:       .github/workflows/ci.yml triggers on push (main + tags v*) and PR
docker:   workflow/Dockerfile.evident-release built locally? NO — only spec
```

## What just landed (uncommitted changes ready to push)

- Replaced `write!(...\n)` with `writeln!(...)` in `treescape-render/src/svg.rs` (clippy)
- Replaced field-reassign-after-default with struct-literal in `treescape-connector/src/py_render.rs` (clippy)
- CI workflow trigger now includes tag pushes (`tags: ['v*']`) so the release-tier ggtree job actually fires
- `release_only` pytest marker registered in workspace `pyproject.toml`; CI uses `-m "not release_only"` for ci-tier and `-m release_only` for release-tier; `tests/oracle/test_layout_vs_ggtree.py` carries the mark
- `workflow/README.md` and `tests/fixtures/trees/FIXTURES.md` corrected to match reality (no more "medium/ is empty" vs primates.nwk contradiction)
- `CONTRIBUTING.md`, `CHANGELOG.md` (v0.1 unreleased), README screenshot of `assets/primates.svg`

## ggtree finally installed (just now)

User-local install at `~/R/library/`. Claim #5 (`treescape-layout-vs-ggtree`) has not yet been run end-to-end against actual ggtree on this machine. Two next steps before tagging:

```bash
# 1. Verify claim #5 locally
R_LIBS_USER=~/R/library /scratch/timsim-demo/treescape/.venv/bin/python -m pytest \
    tests/oracle/test_layout_vs_ggtree.py -v -m release_only

# If conventions diverge: write the gap into docs/conventions.md, then either
# adjust tolerance with rationale OR fix the convention. Do NOT silently bump.

# 2. Build and run the release Docker image (canonical CI path)
docker build -f workflow/Dockerfile.evident-release -t treescape-release .
docker run --rm -v "$PWD:/workspace" -w /workspace treescape-release \
    bash -lc "(cd treescape-connector && maturin develop --release) && \
              pip install -e packages/treescape-reference -e packages/treescape && \
              pytest tests/oracle -v -m release_only"
```

## Tag v0.1.0

After both ggtree paths above are green:

```bash
git commit -am "v0.1.0: ..."   # commit any conventions.md updates from claim #5
git tag -a v0.1.0 -m "treescape v0.1.0 — see CHANGELOG.md"
git push origin main v0.1.0
# CI on the tag push runs both tiers; release artifact gets uploaded to oracle-reports-ci
# Optional: gh release create v0.1.0 -F CHANGELOG.md
```

## Known gaps deferred to v0.2 (already documented in CHANGELOG)

- Circular and radial layouts.
- PDF export.
- Clade highlighting and metadata-driven branch/node styling.
- fontdue-measured tip-label widths (replacing the 0.6-em monospace approximation). The bundled DejaVuSans.ttf is already in `treescape-render/src/fonts/`, so the wire-up is a one-day task.
- Nexus and PhyloXML parsers.
- `treescape-cli` and the `treeplot` console entry point.
- Polars/pandas dual-support; metadata join API.

## v0.2 GPU candidates (saved to memory)

The big one: **label collision avoidance at >10k tips**. Naive O(n²) AABB on 100k tips is ~30s on CPU; CUDA spatial-hash kernel ~30ms. Tree is already SoA and layout coords are parallel `Vec<f64>` — direct GPU upload, no architectural cost. See memory entry `project_treescape_v02_gpu_candidates.md`.

## Repo

https://github.com/theGreatHerrLebert/treescape — public, MIT, evident submodule pinned to `bf990d2`.

## Local dev environment state on this box

- `/scratch/timsim-demo/treescape/.venv/` — Python 3.12 venv with maturin, pytest, hypothesis, biopython 1.87, ete3, treescape_connector (editable), treescape-reference (editable), treescape (editable)
- `~/R/library/` — personal R lib with BiocManager, ggtree, ape (just finished installing during the previous session)
- ggtree install output is at `/tmp/claude-1000/-scratch-timsim-demo-treescape/.../tasks/bcjs06p0i.output` (mostly empty — `tail -8` consumed the stream)
