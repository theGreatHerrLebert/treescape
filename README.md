# treescape

Python-native phylogenetic tree visualization with a Rust core and EVIDENT-style trust scaffolding.

<p align="center">
  <img src="assets/primates.svg" alt="treescape rendering of a 12-tip primate phylogeny" width="640"/>
</p>
<p align="center"><em>Rectangular phylogram, deterministic SVG, byte-identical Rust↔Python reference output. See <a href="assets/gallery/">assets/gallery/</a> for circular layouts, metadata-driven coloring, clade highlights, and feature combinations.</em></p>

## Status

v0.3.0 shipped (2026-04-28). Sixteen EVIDENT claims pinned and green; rectangular and circular layouts; metadata join (polars) with discrete (Tableau-10) and continuous (viridis) tip and branch coloring; clade highlights on both layouts; scale-bar and support-label annotations on rectangular. See `plan.md` and `plan-v0.3.md` for the vision, `CHANGELOG.md` for what landed, and `evident.yaml` for the trust manifest.

## Gallery

`assets/gallery/` shows ten variants on a single 12-tip primate phylogeny — same fixture, same options, one feature toggled per file — so you can compare layouts and styling apples-to-apples. The gallery's [README](assets/gallery/) lists each file with the line of code that produced it.

## Quickstart (development)

```bash
git clone --recursive https://github.com/theGreatHerrLebert/treescape.git
cd treescape
python3.12 -m venv .venv
source .venv/bin/activate
pip install maturin pytest biopython ete3 hypothesis polars fonttools
(cd treescape-connector && maturin develop --release)
pip install -e packages/treescape-reference -e packages/treescape

python -c "from treescape import TreePlot; TreePlot('((a:1,b:1):1,(c:1,d:1):1);').save('/tmp/tree.svg')"
pytest tests/oracle -m "not release_only" -v   # ~180 ci-tier tests; rest skip cleanly when prereqs are missing
```

## Quick architecture

```
Rust:    treescape-core/, treescape-render/
PyO3:    treescape-connector/
Python:  packages/treescape, packages/treescape-reference
```

Mirrors the proven rustims layout (Rust workspace + PyO3 connector cdylib + thin Python packages on top).

## Trust

Every numerical and structural claim made by treescape is pinned in [`evident.yaml`](./evident.yaml) with an oracle, a tolerance, a reproducible command, and a recorded artifact — **before** the code that implements the claim lands. As of v0.3.0, sixteen claims are pinned and green, validated against three independent layout oracles (ete3, Biopython.Phylo, R/ggtree) plus a Python reference implementation that users can `pip install treescape-reference` and verify themselves.

`evident.yaml` is the source of truth for what's claimed and how it's tested. The runners live at `tests/oracle/test_*.py`; ci-tier claims run on every push, the release-tier ggtree claim runs on tag push inside `workflow/Dockerfile.evident-release`. When a prerequisite is absent locally, the corresponding test skips cleanly — it does not silently pass. Run `pytest tests/oracle -v` and read the `SKIPPED` reasons to see which prerequisites are missing in your environment.

## License

MIT
