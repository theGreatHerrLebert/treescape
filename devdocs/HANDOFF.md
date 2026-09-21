# Handoff — v0.6 (updated 2026-09-21)

Plan: `devdocs/plans/plan-v0.6.md` (approved; decisions 1 and 3 at their defaults, 2 and 4 open). v0.5.0 is tagged (`7e5a386`). Delete this file when v0.6.0 is tagged.

## Done

| Commit | What |
|---|---|
| `7e5a386` (tag `v0.5.0`) | v0.5 review round 2 closed; release tier 8/8 run locally in Docker before tagging |
| `a7db379` | v0.6 plan |
| `f059765` | Fix: circular θ of a node with evenly spread children (Rust/reference drift, found by Phase 2) — arc-midpoint rule |
| `55d77f6` | **Phase 2**: pinned random corpus (`layout-v2`, 66 trees), external oracles check Rust + reference node by node, macOS determinism job. Reviewed; findings closed. Release tier 265/265 locally. |
| `81763ca` | **Phase 3**: NJ/UPGMA from distance matrices in Python and Julia, seven claims (oracles scikit-bio, Biopython, SciPy, ape, phangorn; additive recovery; bounded performance), C ABI 2, release runners fail instead of skipping. Code-reviewed; findings fixed. Release tier 555/555. |
| `872a325` | **Phase 1**: manifest on the upstream EVIDENT schema, pinned oracles (`tests/requirements-oracles.txt`), `tests/oracle/test_manifest.py`, named hashed corpora (`tests/fixtures/corpora.toml`), typed-trust claim viewer at `/trust/`. Reviewed by an independent agent; findings closed. |

## Open, in order

1. **Check CI once** for `81763ca` (Phase 3) and the commit after it. The first run of the rewritten ci-tier includes the tree-building oracles (~1 min more) and the Julia parity for trees from distances. `determinism-macos` passed on `55d77f6`, and the docs now say "Linux x86-64 and macOS arm64".
2. **Decisions for the user** (don't edit claim text without them):
   - `treescape-circular-layout-vs-ete3` claims 1e-4 while its runner asserts 1e-6. Tighten the claim?
   - Plan decision 2 answered 2026-09-21: **no MATLAB available.** The MATLAB oracle is dropped and treescape makes no MATLAB-equivalence claim (recorded in the plan and conventions).
   - Plan decision 4, course data: may the course-derived matrices, labels and GenBank accessions be published? The course fixtures, the "Coming from MATLAB" page, and the use of `D.mat` (208 taxa with 6 zero pairs) as a real-world tie fixture all wait on it. The use-case files are in memory (`project_course_use_cases.md`).
3. **Before tagging v0.6.0:** once decision 4 is settled (or explicitly deferred to v0.7), bump the versions to 0.6.0 (Cargo, pyprojects, `Project.toml`, `__version__`; the `treescape` pins in `evident.yaml` then fail `test_manifest.py` until they are updated too). Run the release tier and the `bench` job before the tag (`gh workflow run ci --ref main` runs both), update the CHANGELOG date, and ask the user before pushing the tag.
4. **v0.7 backlog** in `devdocs/plans/v0.6-candidates.md`: faster NJ (user decision), render fidelity and claim consolidation (v0.5 audit), distances from sequences, vertical orientation.

## Environment notes

- Python `.venv` (3.12) has the pinned oracles; after Rust changes: `(cd treescape-connector && maturin develop --release)`.
- Julia: `~/julia/julia-1.12.7/bin/julia` (bare `julia` is 1.10). `TREESCAPE_JULIA`, `TREESCAPE_REQUIRE_JULIA=1`.
- typed-trust: `cargo build --release --manifest-path evident/typed-trust/Cargo.toml`. The MkDocs hook needs it (it renders `/trust/`).
- Full check: `cargo test --workspace && cargo clippy --workspace -- -D warnings && TREESCAPE_JULIA=~/julia/julia-1.12.7/bin/julia TREESCAPE_REQUIRE_JULIA=1 .venv/bin/pytest tests/oracle -m "not release_only" && .venv/bin/python evident/workflow/validate_manifest.py --strict-release-pins evident.yaml && .venv/bin/mkdocs build --strict`.
- Release tier locally: Docker here is a snap and cannot see `/scratch` or hidden `$HOME` dirs. Copy the tracked files to `~/treescape-release-ctx`, then `docker buildx build --builder default --load ...`, then run with `-v` on that copy (recipe in memory `reference_docker_release_tier.md`). Docker commands need the sandbox disabled.
- `gh` is authenticated (repo + workflow scopes): `gh workflow run ci --ref main` runs the release tier before a tag.
- Codex CLI hit its usage limit on 2026-09-21. When it is unavailable, reviews run as independent Claude agents. Frame prompts as "correctness and robustness review" (not "security audit").
