# Handoff — v0.6 (updated 2026-09-21)

Plan: `devdocs/plans/plan-v0.6.md` (approved; decisions 1 and 3 at their defaults, 2 and 4 open). v0.5.0 is tagged (`7e5a386`). Delete this file when v0.6.0 is tagged.

## Done

| Commit | What |
|---|---|
| `7e5a386` (tag `v0.5.0`) | v0.5 review round 2 closed; release tier 8/8 run locally in Docker before tagging |
| `a7db379` | v0.6 plan |
| `872a325` | **Phase 1**: manifest on the upstream EVIDENT schema, pinned oracles (`tests/requirements-oracles.txt`), `tests/oracle/test_manifest.py`, named hashed corpora (`tests/fixtures/corpora.toml`), typed-trust claim viewer at `/trust/`. Reviewed by an independent agent; findings closed. |

## Open, in order

1. **Check CI once** for `872a325` (first run of the rewritten `ci.yml`/`docs.yml`: upstream validator, typed-trust build, pinned oracles) and the `v0.5.0` tag's release-tier run: `gh run list --limit 6`. Then check `/trust/` on the Pages site. One check, no watching.
2. **Decisions for the user** (don't edit claim text without them):
   - The "Noted, not changed" items in the CHANGELOG `[Unreleased]` section: circular-ete3 1e-4 vs the runner's 1e-6; "small and medium fixtures" wording; external-oracle claims naming Rust sources but testing the reference; two inaccurate ete3 sentences. Phase 2 resolves most of them by rewriting those claims' text and inputs.
   - Plan decision 2: can MATLAB (with the Bioinformatics Toolbox) be run once to export the course fixtures' distance matrices and trees as Newick? Decision 4: may course-derived data (distance matrices, labels, GenBank accessions) be published? Both gate only Phase 3.
3. **Phase 2** (plan §Phase 2): pinned random corpus, oracles compare Rust directly, primates + random in every layout claim, macOS leg. From the Phase 1 review: make the runners load their fixture lists from `tests/fixtures/corpora.toml`, so corpus and runner cannot drift apart.
4. **Phase 3**: NJ/UPGMA from distance matrices, speed benchmark. Course use cases are at the Seafile share in memory (`project_course_use_cases.md`).

## Environment notes

- Python `.venv` (3.12) has the pinned oracles; after Rust changes: `(cd treescape-connector && maturin develop --release)`.
- Julia: `~/julia/julia-1.12.7/bin/julia` (bare `julia` is 1.10). `TREESCAPE_JULIA`, `TREESCAPE_REQUIRE_JULIA=1`.
- typed-trust: `cargo build --release --manifest-path evident/typed-trust/Cargo.toml`. The MkDocs hook needs it (it renders `/trust/`).
- Full check: `cargo test --workspace && cargo clippy --workspace -- -D warnings && TREESCAPE_JULIA=~/julia/julia-1.12.7/bin/julia TREESCAPE_REQUIRE_JULIA=1 .venv/bin/pytest tests/oracle -m "not release_only" && .venv/bin/python evident/workflow/validate_manifest.py --strict-release-pins evident.yaml && .venv/bin/mkdocs build --strict`.
- Release tier locally: Docker here is a snap and cannot see `/scratch` or hidden `$HOME` dirs. Copy the tracked files to `~/treescape-release-ctx`, then `docker buildx build --builder default --load ...`, then run with `-v` on that copy (recipe in memory `reference_docker_release_tier.md`). Docker commands need the sandbox disabled.
- `gh` is authenticated (repo + workflow scopes): `gh workflow run ci --ref main` runs the release tier before a tag.
- Codex CLI hit its usage limit on 2026-09-21. When it is unavailable, reviews run as independent Claude agents. Frame prompts as "correctness and robustness review" (not "security audit").
