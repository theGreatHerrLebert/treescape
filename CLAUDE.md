# CLAUDE.md

Coherence notes for AI-assisted development of treescape.

## What this project is

A Python-native phylogenetic tree visualization library with a Rust core and EVIDENT-style trust scaffolding. See `plan.md` for the vision, `evident.yaml` for the active trust manifest, and `~/.claude/plans/stateless-waddling-crane.md` for the v0.1 implementation plan.

## Architecture you must mirror

The repo follows the rustims layout exactly (`/scratch/timsim-demo/SUBMISSION/rustims/`). Read its `Cargo.toml`, `imspy_connector/src/lib.rs`, and `imspy_connector/pyproject.toml` before changing build files here.

- Two pure-Rust crates: `treescape-core` (fat capability — tree, parsers, traversal, layout, scene graph) and `treescape-render` (SVG emitter + themes).
- One PyO3 connector cdylib: `treescape-connector`. Use `wrap_pymodule!` submodules (`py_tree`, `py_layout`, `py_render`, `py_metadata`), not a single flat module.
- Python packages live under `packages/`: `treescape` (user-facing TreePlot grammar), `treescape-reference` (slow, readable Python — the EVIDENT oracle for layout), `treescape-cli` (deferred to v0.3).

## Internal tree representation

Struct-of-arrays in Rust. Parallel `Vec<usize> parent_idx`, `Vec<f64> branch_len`, `Vec<String> name`, `Vec<bool> is_tip`, `Vec<Option<u32>> meta_idx`. Index-based API. Do **not** introduce `Vec<Node>` arenas — that decision was made deliberately for cache behavior and Arrow-FFI friendliness.

## Renderer

Pure-Rust SVG. No matplotlib. Use `fontdue` or `ttf-parser` for real text bbox measurement; bundle one font (DejaVu Sans) for v0.1 and document the limitation. Output must be byte-deterministic — sorted attributes, no timestamps, fixed float formatting.

## EVIDENT discipline

- Claims are pinned in `evident.yaml` **before** the code that backs them lands. The `treescape-reference` Python implementation must exist before the Rust port for any layout claim — the oracle precedes the code.
- Three external layout oracles (ete3, Biopython, ggtree) come from independent lineages. Their *agreement* is strong evidence; their *disagreement* is the more interesting signal — document it in `docs/conventions.md`, never silently absorb it with tolerance bumps.
- `release`-tier claims (e.g. ggtree, which needs R+Bioconductor) must run before any release tag inside the heavier validation image; they cannot be skipped.
- Property-style invariants (tip-count, coordinate bounds, SVG determinism) are part of the manifest, not separate "extra tests."

## v0.1 scope discipline

Tight: Newick + rectangular only + tip labels + SVG + one theme + `join_metadata` + tip color by metadata. Anything else (circular, PDF, clade highlighting, branch/node styling, Nexus, PhyloXML, polars dual-support, CLI, Jupyter rich display) is v0.2+. Resist scope creep — the plan was deliberately cut tight after a critique that an over-wide MVP is months-and-abandonment-risk.

## When implementing layout

Write `treescape-reference` (Python) first. Then port to Rust. This order is deliberate: the readable Python is the oracle the Rust must agree with. Reversing the order makes the Rust↔Python parity claim circular.

## Files / conventions

- Rust crate names use hyphens (`treescape-core`); Cargo lib names and Python imports use underscores (`treescape_core`).
- Workspace deps live in the root `Cargo.toml` `[workspace.package]` block — version, edition, license inherit from there.
- Python packages live at `packages/<name>/src/<name>/...` (src-layout).
- Fixtures are versioned and referenced by ID from `evident.yaml` (`tests/fixtures/trees/`).
