# NEXT — pick up here

Working notes for resuming v0.2 ship work. Delete or merge into CHANGELOG once tagged.

## Where we are

v0.2 phases 1–3 are **landed on main but not tagged**. CI is green again after three fixes today.

```
phases:    1✓ 2✓ 3✓
claims:    11 pinned + green (was 8 in v0.1)
tests:     42 core + 11 render Rust unit; 166 pytest pass + 8 release_only deselected
manifest:  validate_manifest.py green
clippy:    clean (-D warnings)
ci/cd:     ✓ Rust workspace, ✓ ci-tier oracle claims, release-tier skipped (fires on tag push only)
```

## What landed since v0.1.0

- **Phase 1 (`72c9d4b`)** — fontdue tip-label widths replace v0.1's 0.6-em monospace approximation; new claim `treescape-text-width-vs-fontdue` (ci-tier). API change: dropped `avg_glyph_width` from the Python surface.
- **Phase 2 (`5b7df9c` + `2bb9d50`)** — circular layout end-to-end. Polar `(r, θ)` per node, byte-deterministic SVG with arc spines + radial branches + rotated tip labels. Two new claims (`treescape-circular-layout-vs-ete3` ci-tier, `treescape-circular-layout-vs-ggtree` release-tier). Two real ggtree convention divergences documented in `docs/conventions.md` (CCW vs CW sweep, default ladderize) — not absorbed into tolerances.
- **Phase 3 (`0cbc166`)** — `TreePlot.highlight_clade(tips=, color=, alpha=)` + `TreePlot.color_tips({...})`; new claim `treescape-styling-determinism` (ci-tier, property-style). Rectangular only; circular + styling raises `NotImplementedError` cleanly.
- **CI fixes** (`b87f716`, `189f3db`, `436ab09`) — see "What CI taught us" below.

## What CI taught us (and is now fixed in main)

Three independent failures had to be unstuck before the post-v0.1.0 commits could be considered shippable:

1. `actions/checkout@v4` with `submodules: recursive` was descending into `evident/`'s nested case-study submodules (`cu-ims-primitives` is private/missing). All three jobs now use `submodules: true`.
2. `maturin develop --release` requires an active venv; `actions/setup-python` doesn't make one. Replaced with `pip install -e ./treescape-connector` (PEP 517 path, no venv check).
3. `workflow/validate_manifest.py` imports `yaml`; `PyYAML` was in the Dockerfile but missing from the CI runner's pip install line. Added.

If anything similar surfaces, the same three places are the usual suspects.

## Two next steps before tagging v0.2.0

```bash
# 1. External review of the v0.2 changes (per the cadence memory:
#    review per phase, address findings before any release tag).
#    Target: the four post-v0.1.0 commits — fontdue widths, circular
#    coords, circular rendering+oracles, clade highlighting+styling.
#    Recurring v0.1 review findings to look for:
#      - claim overstatement vs what the test actually checks
#      - undeclared test deps (the fontTools / hypothesis lineage)
#      - silent tolerance bumps where a documented convention gap belongs
git log --oneline 7b5a6f8..HEAD   # commits to review

# 2. Once findings are closed: tag.
git tag -a v0.2.0 -m "treescape v0.2.0 — see CHANGELOG.md"
git push origin main v0.2.0
# CI on the tag push runs the release-tier ggtree jobs (rectangular +
# circular) inside workflow/Dockerfile.evident-release.
# Optional: gh release create v0.2.0 -F CHANGELOG.md
```

## Known gaps deferred to v0.3 (already in CHANGELOG)

- **Circular clade highlighting.** v0.2 raises `NotImplementedError` cleanly when `.layout("circular")` is combined with `.highlight_clade`/`.color_tips`. The annular-sector path geometry is not trivial.
- **`join_metadata` API + metadata-driven branch/node coloring.** Hard requirement is decided up front: polars or pandas dual-support? (Plan said both; v0.3 should pick one as primary.) Without `join_metadata`, `color_branches_by(metadata_col=...)` cannot exist.
- **Branch-stroke and node-shape styling.**
- **PDF export.** Same scene graph; new emitter.
- **Nexus and PhyloXML parsers.**
- **`treescape-cli` / `treeplot` console.**
- **fontdue: kerning + non-Latin shaping.** v0.2 is sum-of-advance-widths only.

## v0.2+ GPU candidates (still in memory)

The big one: **label collision avoidance at >10k tips**. Naive O(n²) AABB on 100k tips ≈ 30 s on CPU; CUDA spatial-hash kernel ≈ 30 ms. Tree is already SoA and layout coords are parallel `Vec<f64>` — direct GPU upload, no architectural cost. See memory entry `project_treescape_v02_gpu_candidates.md`.

## Repo

https://github.com/theGreatHerrLebert/treescape — public, MIT, evident submodule pinned to `bf990d2`.

## Local dev environment state on this box

- `/scratch/timsim-demo/treescape/.venv/` — Python 3.12 venv. `maturin develop --release` for connector iter, `pip install -e packages/treescape-reference` etc. fonttools added.
- `~/R/library/` — personal R lib with BiocManager, ggtree 4.0.5, ape, etc. (R 4.5.3 from `update.sh` earlier this session.)
- Docker image `treescape-release:latest` built locally (~2.16 GB). Run with `-v ~/treescape-docker-run:/workspace` because snap-confined docker can't see `/scratch`. Use `rsync -a --delete --exclude=.venv --exclude=target --exclude=.git /scratch/timsim-demo/treescape/ ~/treescape-docker-run/` to refresh the mirror before each docker run.
