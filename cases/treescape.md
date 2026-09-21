# Case: treescape — Python phylogenetic tree visualization with Rust core

## Component

`treescape` is a phylogenetic tree visualization library with a Rust core (`treescape-core`, `treescape-render`), PyO3 bindings for Python (`treescape-connector` → `packages/treescape`) and C-ABI bindings for Julia (`treescape-jl-connector` → `packages/Treescape.jl`). As of v0.5 it covers Newick parsing, rectangular and circular layouts, deterministic SVG output, and metadata-driven styling (tip and branch color, branch width, clade highlights, scale bars, support labels).

## What is being claimed

The library produces tree visualizations whose underlying numerical and structural operations — Newick parsing, rectangular layout coordinate construction, ladderization, and SVG emission — are correct in the sense defined by the EVIDENT framework: every claim points to an oracle, a tolerance, a reproducible command, and a recorded artifact.

## Why this case is interesting

Tree layout is a quietly numerical operation. Two libraries can produce visually similar phylograms whose tip y-coordinates disagree by several pixels because of subtly different conventions (tip-spacing rules, internal-node placement, root-x choice). Most users never notice. For a publication-grade figure tool, that gap is a correctness bug — and it is invisible to test-passing-illusion-style validation.

This case applies the EVIDENT pattern of layered, independent-lineage oracle comparison:

- **Reference shadowing** — a slow, readable Python implementation (`treescape-reference`, separately PyPI-publishable) is the canonical convention owner. The Rust core must agree within `1e-9`.
- **External oracles from independent code lineages** — ete3 (CSIC), Biopython.Phylo (Biopython), and R/ggtree (Bioconductor + ggplot2) for rectangular layout; ete3 and R/ggtree for circular layout (Biopython has no circular layout). They check both the Rust core and the Python reference, node by node, on the `layout-v2` corpus: 66 trees of 2–200 tips, including a pinned random corpus. Their agreement is strong evidence; their disagreement is documented as a convention gap and never silently absorbed by tolerance bumps.
- **Determinism** — same input + same options → byte-identical SVG output across runs. Pinned as a proof-by-construction claim.
- **Binding fidelity** — the Julia package and the Python package drive the same Rust core and must emit byte-identical SVG for the same inputs, including every example on the docs site. This shows the host layers add nothing and lose nothing; it is deliberately not counted as independent evidence of correctness.
- **Robustness at the language boundary** — malformed input through the Julia C ABI must return an error, never abort the host process (fuzzed, and run under Miri).

## Trust strategy

Predominantly **validation**, with a small **proof-by-construction** component (SVG determinism). Claims gate releases via tier (`ci` vs `release`). The `release`-tier ggtree oracle requires R + Bioconductor and runs only inside the heavier validation image: manually on `main` before tagging, and again when the `v*` release tag is pushed.

## Source

[This repository](https://github.com/theGreatHerrLebert/treescape) — the entire workspace is the source for this case. Specific files implementing each claim are listed in `evident.yaml`.

## Failure modes the manifest is designed to surface

- Newick edge cases (negative branches, NHX, quoted names, trifurcation roots) silently parsed differently across libraries.
- Layout convention drift between Rust and the Python reference, undetected because both are ours.
- Three external oracles agreeing only because they share a heritage (the Agreement Trap — explicitly addressed by picking three lineages that don't).
- SVG output drifting between runs or platforms because of float formatting or HashMap iteration order, breaking figure reproducibility. (Cross-platform determinism is currently verified on Linux only.)
