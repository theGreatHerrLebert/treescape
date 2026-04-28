# treescape

Python-native phylogenetic tree visualization with a Rust core and EVIDENT-style trust scaffolding.

<p align="center">
  <img src="assets/primates.svg" alt="treescape rendering of a 12-tip primate phylogeny" width="640"/>
</p>
<p align="center"><em>v0.1: rectangular phylogram, deterministic SVG, byte-identical Rust↔Python reference output.</em></p>

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

All eight claims are implemented. Status here is reported relative to a local environment that has the prerequisites listed in **Quickstart** (Python 3.11+, the maturin-built `treescape_connector`, Biopython, ete3, and hypothesis). When a prerequisite is absent, the corresponding test skips cleanly — it does not silently pass.

| Claim | Tier | Requires | Status (with prereqs) |
|---|---|---|---|
| treescape-newick-roundtrip | ci | Biopython, connector | green |
| treescape-layout-rust-vs-reference | ci | connector | green |
| treescape-layout-vs-ete3 | ci | ete3 | green |
| treescape-layout-vs-biopython | ci | Biopython (≥1.84) | green |
| treescape-layout-vs-ggtree | release | R + Bioconductor + ggtree | green inside `workflow/Dockerfile.evident-release`; skips on `ci` |
| treescape-ladderize-order | ci | ete3 | green |
| treescape-svg-determinism | ci | connector | green |
| treescape-tip-count-invariant | ci | hypothesis | green |

Run `pytest tests/oracle -v` and read the `SKIPPED` reasons to see which prerequisites are missing in your environment.

## License

MIT
