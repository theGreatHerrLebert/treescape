# Case: treescape — Python phylogenetic tree visualization with Rust core

## Component

`treescape` is a Python-native phylogenetic tree visualization library with a Rust core (`treescape-core`, `treescape-render`) and PyO3 bindings (`treescape-connector`). v0.1 focuses on Newick parsing, rectangular layouts, deterministic SVG output, and metadata-driven tip styling.

## What is being claimed

The library produces tree visualizations whose underlying numerical and structural operations — Newick parsing, rectangular layout coordinate construction, ladderization, and SVG emission — are correct in the sense defined by the EVIDENT framework: every claim points to an oracle, a tolerance, a reproducible command, and a recorded artifact.

## Why this case is interesting

Tree layout is a quietly numerical operation. Two libraries can produce visually similar phylograms whose tip y-coordinates disagree by several pixels because of subtly different conventions (tip-spacing rules, internal-node placement, root-x choice). Most users never notice. For a publication-grade figure tool, that gap is a correctness bug — and it is invisible to test-passing-illusion-style validation.

This case applies the EVIDENT pattern of layered, independent-lineage oracle comparison:

- **Reference shadowing** — a slow, readable Python implementation (`treescape-reference`, separately PyPI-publishable) is the canonical convention owner. The Rust core must agree within `1e-9`.
- **Three external oracles from independent code lineages** — ete3 (CSIC), Biopython.Phylo (Biopython), and R/ggtree (Bioconductor + ggplot2). Their agreement is strong evidence; their disagreement is documented as a convention gap and never silently absorbed by tolerance bumps.
- **Determinism** — same input + same options → byte-identical SVG output across runs and platforms. Pinned as a proof-by-construction claim.

## Trust strategy

Predominantly **validation**, with a small **proof-by-construction** component (SVG determinism). Claims gate releases via tier (`ci` vs `release`). The `release`-tier ggtree oracle requires R + Bioconductor and runs only inside the heavier validation image before tagging.

## Source

`/scratch/timsim-demo/treescape/` — the entire workspace is the source for this case. Specific files implementing each claim are listed in `evident.yaml`.

## Failure modes the manifest is designed to surface

- Newick edge cases (negative branches, NHX, quoted names, trifurcation roots) silently parsed differently across libraries.
- Layout convention drift between Rust and the Python reference, undetected because both are ours.
- Three external oracles agreeing only because they share a heritage (the Agreement Trap — explicitly addressed by picking three lineages that don't).
- SVG output drifting across platforms because of float formatting or HashMap iteration order, breaking figure reproducibility.
