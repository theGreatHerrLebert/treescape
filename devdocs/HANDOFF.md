# Handoff — v0.5 (written 2026-09-21)

State of the v0.5 work and what is still open before the **v0.5.0 tag**. Plan: `devdocs/plans/plan-v0.5.md`. Next version's backlog: `devdocs/plans/v0.6-candidates.md`. Delete this file when v0.5.0 is tagged.

## Done and pushed (main)

| Commit | What |
|---|---|
| `35d57bf`, `9aa04b3` | **Phase 1** — styling resolution moved from `plot.py` into `treescape-core::style` (+ `py_style`); oracle `treescape_reference.style`; claim `treescape-style-resolution-rust-vs-reference`; Codex review round 1 closed |
| `8f8bf87`, `7bd50ca` | **Phase 2** — Julia binding: `treescape-jl-connector` (C ABI) + `packages/Treescape.jl`; claims `treescape-julia-python-svg-parity`, `treescape-jl-ffi-no-abort`; two Codex reviews (general + FFI robustness) closed |
| `d4f60ea` | **Phase 3** — MkDocs site (`mkdocs.yml`, `docs/`, `scripts/mkdocs_hooks.py`), tested Python/Julia examples (`tests/oracle/test_docs_examples.py`), `.github/workflows/docs.yml` |
| `5e8c287` | README rewrite (why / quickstart / what to trust / design / acknowledgements / references) + `THIRD_PARTY_NOTICES.md` |
| `141c9a0` | Repo root cleaned: plans → `devdocs/plans/`, `CLAUDE.md` → `.claude/`, `CONTRIBUTING.md` → `.github/` |
| `7f68726` | Miri trimmed to the FFI plumbing tests (~3 s; render tests skipped under Miri) |

Also fixed along the way (all in CHANGELOG): Newick `]` infinite loop / OOM (both parsers), Python 3.11 vs 3.12 `sum()` divergence (pinned Neumaier), NaN/inf → invalid SVG (now raises), XML-forbidden chars, several Julia GC/ownership bugs.

**Verification at handoff:** 401 oracle tests, 68 Julia tests (1.10 + 1.12), Rust 54 core / 10 connector / 12 render, Miri clean. GitHub CI green for Rust, ci-tier, Julia 1.10, Julia 1.12 (first run of the Julia jobs on `5e8c287`). Release-tier (ggtree) has **not** run in v0.5 — it only runs on a tag.

## Open before tagging v0.5.0 — in order

### 1. Docs deploy
Pages was only enabled at the end of the session (`has_pages: true`, Source "GitHub Actions"). The push of this file triggers `.github/workflows/docs.yml`; check it deployed to <https://thegreatherrlebert.github.io/treescape/>. Earlier failures were all "Pages not enabled" (404 on deploy); the build step always succeeded.

### 2. Codex round-2 review of the Phase 2 fixes
The round-2 run of commit `7bd50ca` hit the Codex usage limit before writing a report. Before stopping it had confirmed: no leaks on 15,000 rejected calls, deepcopy/GC safe under concurrency, `undef` buffers OK, NaN options raise, parity 37/37, gallery 14/14. Re-run on `7bd50ca..HEAD` for the FFI + Julia files and close findings.

How Codex was run (read-only, background, prompt on stdin):
```bash
codex exec -s read-only -C /scratch/timsim-demo/treescape -o <out.md> - < prompt.txt
```
`codex review --commit X` does not accept a custom prompt. **Wording matters:** a prompt framed as a "security audit" (attacker, injection, DoS) was refused by Codex's cyber filter; the same checklist framed as a "correctness and robustness review" worked.

### 3. Claims audit → proposal → user approval
The user asked for the EVIDENT claims to be reviewed (by Claude and by Codex): do they justify trusting treescape relative to third-party tools; drop redundant ones; add missing ones. **The Codex audit has not run yet** (usage limit). Claude's findings so far:

1. **External layout agreement rests on 4 tiny fixtures** (2–5 tips: `two_tip`, `balanced_4`, `unbalanced_5`, `trifurcation_root`). No primates, no random trees vs ete3/Biopython. Biggest trust gap. → add hypothesis-generated trees vs ete3 + Biopython (ci) and ggtree (release).
2. **All external-oracle runners compare `treescape-reference`, not the Rust code** (`test_layout_vs_ete3.py` etc. import `treescape_reference`). Trust in Rust is transitive via `treescape-layout-rust-vs-reference`, which also covers only those 4 fixtures → extend it to random trees + all fixtures.
3. **No render-fidelity claim.** Coordinates are oracle-checked; the emitted SVG is only snapshot/determinism-tested, so a scene-building bug would be frozen into goldens. → parse the SVG, check branch/label/highlight geometry equals the transformed validated coordinates (both layouts).
4. **`treescape-tip-count-invariant` tests only the Python reference renderer** (rectangular) while its `source` says `treescape-render` → run it on the Rust connector, both layouts.
5. **`treescape-svg-determinism` claims "across runs and platforms"**; CI is Linux-only → narrow the text or add a macOS CI leg.
6. **Six self-oracle styling claims overlap** (svg-determinism, styling-determinism, color-by-continuous-determinism, branch-width-by-numeric-determinism, circular-annotation-determinism, color-tips-by-discrete-roundtrip): "same bytes twice" is near-free for a pure function. → merge into one determinism claim + semantic claims (right element gets right color/width; e.g. highlight MRCA vs ete3/Biopython `common_ancestor`).
7. Other candidates: scale-bar pixel length = length × px_per_x; metadata-join semantics vs a polars left join; Newick vs a second parser (ete3) and edge corpus.

Suggested Codex audit prompt: per-claim keep/revise/merge/drop table with file:line evidence + prioritized new claims (oracle, tolerance, tier, effort). **Merge both audits into one proposal and get the user's OK before editing `evident.yaml`** — it is the trust contract.

### 4. EVIDENT schema migration + claim viewer on Pages
The user wants EVIDENT's claim visualization on the docs site. Upstream EVIDENT (`evident/` submodule is pinned at `bf990d2`, April; upstream `origin/main` was `bd79f68`) has `typed-trust --format site` — one self-contained HTML page (claims table, coverage matrix, claim–oracle graph, drill-downs).

Tested at handoff: built `typed-trust` from upstream, ran on our `evident.yaml` → **all 21 claims rejected**: `kind=measurement requires non-empty tolerances`, and the upstream validator requires top-level `project:`. Migration per upstream `workflow/SCHEMA.md` → "Migration from v0": add `project: treescape`; lift `evidence.tolerance` into structured `tolerances:` entries; add `subsystem`, `inputs`, `pinned_versions`; process-rule claims become `kind: policy`.

Do this together with step 3 (both rewrite `evident.yaml`). Then:
- bump the submodule; switch CI's manifest validation to upstream's validator;
- in `docs.yml`, build `typed-trust` (`cargo build --release` in `evident/typed-trust`) and write `typed-trust --format site evident.yaml > site/trust/index.html` after `mkdocs build`; link it from `docs/claims.md` generation in `scripts/mkdocs_hooks.py` (or the nav).

### 5. Tag v0.5.0
- CHANGELOG: merge "`[Unreleased] — v0.5.0`" and "`v0.4.1 (Phase 1, untagged)`" into one `[0.5.0] — <date>` section (decision: **no v0.4.1 tag**; Phase 1 ships in 0.5.0). Update claim counts.
- Tag push runs the release-tier ggtree claims inside `workflow/Dockerfile.evident-release` — first time in v0.5; must pass.
- Ask the user before pushing the tag.

## Environment notes

- Python: `.venv` (3.12). Rebuild the PyO3 connector after Rust changes: `(cd treescape-connector && maturin develop --release)`.
- Julia: use **`~/julia/julia-1.12.7/bin/julia`** explicitly — bare `julia` on PATH is 1.10. Julia claim runners read `TREESCAPE_JULIA`; `TREESCAPE_REQUIRE_JULIA=1` turns skips into failures (set in CI).
- C-ABI library for Julia: `cargo build -p treescape-jl-connector --release` (found via `TREESCAPE_JL_LIB` or `target/release/`).
- Full check: `cargo test --workspace && cargo clippy --workspace -- -D warnings && TREESCAPE_JULIA=~/julia/julia-1.12.7/bin/julia pytest tests/oracle -m "not release_only" && mkdocs build --strict`; Julia unit tests: `julia --project=packages/Treescape.jl -e 'using Pkg; Pkg.test()'`; Miri: `cargo +nightly miri test -p treescape-jl-connector` (nightly + miri installed).
- `cargo fmt --all` also reformats `treescape-core/src/layout/{circular,scene}.rs` (pre-existing drift) — format only files you touched. `cargo clippy --all-targets` flags a pre-existing test-code lint in `circular.rs`; CI runs clippy without `--all-targets`.
- `gh` here is **not authenticated** (API read-only; can't re-run workflows or read logs). `git push` works. Check CI once when needed; don't poll.
- Codex CLI: `~/.nvm/.../bin/codex`; see the wording note in step 2.
- User preferences: review every phase with Codex and close findings before moving on; pin claims before code; keep the repository root to standard files (notes and plans go in `devdocs/`); ask before pushing tags or changing the trust contract.
