# treescape

Python-native phylogenetic tree visualization with a Rust core and EVIDENT-style trust scaffolding.

## Status

v0.1 in development. See `plan.md` for the vision and `evident.yaml` for the trust manifest.

## Quickstart (development)

```bash
git clone --recursive https://github.com/theGreatHerrLebert/treescape.git
cd treescape
python3.12 -m venv .venv
source .venv/bin/activate
pip install maturin pytest biopython ete3 hypothesis
(cd treescape-connector && maturin develop --release)
pip install -e packages/treescape-reference -e packages/treescape

python -c "from treescape import TreePlot; TreePlot('((a:1,b:1):1,(c:1,d:1):1);').save('/tmp/tree.svg')"
pytest tests/oracle -v          # 64 tests should pass; 4 skip without R/ggtree
```

## Quick architecture

```
Rust:    treescape-core/, treescape-render/
PyO3:    treescape-connector/
Python:  packages/treescape, packages/treescape-reference
```

Mirrors the proven rustims layout (Rust workspace + PyO3 connector cdylib + thin Python packages on top).

## Trust

Every numerical and structural claim made by treescape is pinned in [`evident.yaml`](./evident.yaml) with an oracle, a tolerance, a reproducible command, and a recorded artifact — **before** the code that implements the claim lands. v0.1 will ship with eight claims validated against three independent layout oracles (ete3, Biopython.Phylo, R/ggtree) plus a Python reference implementation that users can `pip install treescape-reference` and verify themselves.

The manifest is pinned today; the oracle test runners turn green progressively as the implementation phases land. See `~/.claude/plans/stateless-waddling-crane.md` for the phase plan and `evident/` for the framework this manifest is written against.

### Claim status

| Claim | Tier | Phase gate | Status |
|---|---|---|---|
| treescape-newick-roundtrip | ci | Phase 1 | green |
| treescape-layout-rust-vs-reference | ci | Phase 4 | green |
| treescape-layout-vs-ete3 | ci | Phase 2 | green |
| treescape-layout-vs-biopython | ci | Phase 2 | green |
| treescape-layout-vs-ggtree | release | Phase 2 (skips on `ci`) | implemented; skips when ggtree absent |
| treescape-ladderize-order | ci | Phase 2 | green |
| treescape-svg-determinism | ci | Phase 3 | green |
| treescape-tip-count-invariant | ci | Phase 3 | green |

## License

MIT
