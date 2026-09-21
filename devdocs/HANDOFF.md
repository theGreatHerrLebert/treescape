# Handoff — v0.6 (updated 2026-09-21)

Plan: `devdocs/plans/plan-v0.6.md` (approved; decisions 1 and 3 at their defaults, 2 and 4 open). v0.5.0 is tagged (`7e5a386`). Delete this file when v0.6.0 is tagged.

## Done

| Commit | What |
|---|---|
| `7e5a386` (tag `v0.5.0`) | v0.5 review round 2 closed; release tier 8/8 run locally in Docker before tagging |
| `a7db379` | v0.6 plan |
| `f059765` | Fix: circular θ of a node with evenly spread children (Rust/reference drift, found by Phase 2) — arc-midpoint rule |
| `55d77f6` | **Phase 2**: pinned random corpus (`layout-v2`, 66 trees), external oracles check Rust + reference node by node, macOS determinism job. Reviewed; findings closed. Release tier 265/265 locally. |
| `872a325` | **Phase 1**: manifest on the upstream EVIDENT schema, pinned oracles (`tests/requirements-oracles.txt`), `tests/oracle/test_manifest.py`, named hashed corpora (`tests/fixtures/corpora.toml`), typed-trust claim viewer at `/trust/`. Reviewed by an independent agent; findings closed. |

## Open, in order

1. **Check CI once** for `55d77f6`: the first run of the `determinism-macos` job. If it passes, change "verified on Linux" to "Linux and macOS" in `README.md` ("Known limits"), `docs/index.md` and `cases/treescape.md`. If it fails, that is a real cross-platform byte finding: investigate, don't paper over it. (Phase 1 CI, the v0.5.0 tag run and `/trust/` were all verified green.)
2. **Decisions for the user** (don't edit claim text without them):
   - CHANGELOG "Noted, not changed": circular-ete3 claims 1e-4 while its runner asserts 1e-6 (tighten the claim?). The other Phase 1 items were resolved in Phase 2.
   - Plan decision 2: can MATLAB (with the Bioinformatics Toolbox) be run once to export the course fixtures' distance matrices and trees as Newick? Decision 4: may course-derived data (distance matrices, labels, GenBank accessions) be published? Both gate only Phase 3.
3. **Phase 3**: NJ/UPGMA from distance matrices, speed benchmark. Course use cases are at the Seafile share in memory (`project_course_use_cases.md`).

## Environment notes

- Python `.venv` (3.12) has the pinned oracles; after Rust changes: `(cd treescape-connector && maturin develop --release)`.
- Julia: `~/julia/julia-1.12.7/bin/julia` (bare `julia` is 1.10). `TREESCAPE_JULIA`, `TREESCAPE_REQUIRE_JULIA=1`.
- typed-trust: `cargo build --release --manifest-path evident/typed-trust/Cargo.toml`. The MkDocs hook needs it (it renders `/trust/`).
- Full check: `cargo test --workspace && cargo clippy --workspace -- -D warnings && TREESCAPE_JULIA=~/julia/julia-1.12.7/bin/julia TREESCAPE_REQUIRE_JULIA=1 .venv/bin/pytest tests/oracle -m "not release_only" && .venv/bin/python evident/workflow/validate_manifest.py --strict-release-pins evident.yaml && .venv/bin/mkdocs build --strict`.
- Release tier locally: Docker here is a snap and cannot see `/scratch` or hidden `$HOME` dirs. Copy the tracked files to `~/treescape-release-ctx`, then `docker buildx build --builder default --load ...`, then run with `-v` on that copy (recipe in memory `reference_docker_release_tier.md`). Docker commands need the sandbox disabled.
- `gh` is authenticated (repo + workflow scopes): `gh workflow run ci --ref main` runs the release tier before a tag.
- Codex CLI hit its usage limit on 2026-09-21. When it is unavailable, reviews run as independent Claude agents. Frame prompts as "correctness and robustness review" (not "security audit").
