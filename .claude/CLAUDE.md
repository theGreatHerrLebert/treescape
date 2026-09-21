# CLAUDE.md

Coherence notes for AI-assisted development of treescape.

## What this project is

A phylogenetic tree visualization library for Python and Julia with a Rust core and EVIDENT-style trust scaffolding. `evident.yaml` is the active trust manifest; per-version plans live in `devdocs/plans/` (`plan-v0.1.md` holds the original vision; the newest `plan-v0.N.md` is the current one); `docs/conventions.md` pins every convention; `CHANGELOG.md` records what landed. Keep the repository root for standard files only — plans, notes and scratch documents go under `devdocs/`.

## Resuming work

If `devdocs/HANDOFF.md` exists, read it first: it lists what is open from the last session, in order.

## Architecture you must mirror

The repo follows the rustims layout exactly (`/scratch/timsim-demo/SUBMISSION/rustims/`). Read its `Cargo.toml`, `imspy_connector/src/lib.rs`, and `imspy_connector/pyproject.toml` before changing build files here.

- Two pure-Rust crates: `treescape-core` (fat capability — tree, parsers, traversal, layout, scene graph) and `treescape-render` (SVG emitter + themes).
- One PyO3 connector cdylib: `treescape-connector`. Use `wrap_pymodule!` submodules (`py_tree`, `py_layout`, `py_render`, `py_metadata`, `py_style`), not a single flat module.
- One C-ABI connector cdylib for Julia: `treescape-jl-connector` (the rustims `imsjl_connector` pattern). It must never panic across the boundary — see its clippy deny-list and the "Julia binding" section of `docs/conventions.md`.
- Packages live under `packages/`: `treescape` (Python TreePlot grammar), `treescape-reference` (slow, readable Python — the EVIDENT oracle), `Treescape.jl` (Julia; must stay byte-identical to Python).

## Internal tree representation

Struct-of-arrays in Rust. Parallel `Vec<usize> parent_idx`, `Vec<f64> branch_len`, `Vec<String> name`, `Vec<bool> is_tip`, `Vec<Option<u32>> meta_idx`. Index-based API. Do **not** introduce `Vec<Node>` arenas — that decision was made deliberately for cache behavior and Arrow-FFI friendliness.

## Renderer

Pure-Rust SVG. No matplotlib. Use `fontdue` or `ttf-parser` for real text bbox measurement; bundle one font (DejaVu Sans) for v0.1 and document the limitation. Output must be byte-deterministic — sorted attributes, no timestamps, fixed float formatting.

## EVIDENT discipline

- Claims are pinned in `evident.yaml` **before** the code that backs them lands. The `treescape-reference` Python implementation must exist before the Rust port for any layout claim — the oracle precedes the code.
- Three external layout oracles (ete3, Biopython, ggtree) come from independent lineages. Their *agreement* is strong evidence; their *disagreement* is the more interesting signal — document it in `docs/conventions.md`, never silently absorb it with tolerance bumps.
- `release`-tier claims (e.g. ggtree, which needs R+Bioconductor) must run before any release tag inside the heavier validation image; they cannot be skipped.
- Property-style invariants (tip-count, coordinate bounds, SVG determinism) are part of the manifest, not separate "extra tests."

## Scope discipline

Each minor version has a tight, written scope in its `devdocs/plans/plan-v0.N.md`, including an explicit "NOT in this version" list. Resist scope creep: the original v0.1 plan was cut tight after a critique that an over-wide MVP is months-and-abandonment-risk, and every version since has kept that cadence (plan → conventions → claims → reference → Rust → review).

## When implementing layout

Write `treescape-reference` (Python) first. Then port to Rust. This order is deliberate: the readable Python is the oracle the Rust must agree with. Reversing the order makes the Rust↔Python parity claim circular.

## Files / conventions

- Rust crate names use hyphens (`treescape-core`); Cargo lib names and Python imports use underscores (`treescape_core`).
- Workspace deps live in the root `Cargo.toml` `[workspace.package]` block — version, edition, license inherit from there.
- Python packages live at `packages/<name>/src/<name>/...` (src-layout).
- Fixtures are versioned and referenced by ID from `evident.yaml` (`tests/fixtures/trees/`).
