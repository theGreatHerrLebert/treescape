# treescape

Python-native phylogenetic tree visualization with a Rust core and EVIDENT-style trust scaffolding.

## Status

v0.1 in development. See `plan.md` for the vision and `evident.yaml` for the trust manifest.

## Quick architecture

```
Rust:    treescape-core/, treescape-render/
PyO3:    treescape-connector/
Python:  packages/treescape, packages/treescape-reference
```

Mirrors the proven rustims layout (Rust workspace + PyO3 connector cdylib + thin Python packages on top).

## Trust

Every numerical and structural claim made by treescape is pinned in [`evident.yaml`](./evident.yaml) with an oracle, a tolerance, a reproducible command, and a recorded artifact. v0.1 ships with eight claims validated against three independent layout oracles (ete3, Biopython.Phylo, R/ggtree) plus a Python reference implementation that users can `pip install treescape-reference` and verify themselves.

See [`evident/`](./evident/) for the framework this manifest is written against.

## License

MIT
