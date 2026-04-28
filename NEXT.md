# NEXT — pick up here

Working notes for resuming v0.2 ship work. Delete or merge into CHANGELOG once tagged.

## Where we are

v0.2 phases 1–3 are **landed on main but not tagged**. CI is green. External review round 1 is **done; fixes are on disk but uncommitted** — see "Review round 1" below before tagging.

```
phases:    1✓ 2✓ 3✓
review:    round 1 ✓ (5 findings: 2×P1, 3×P2 — all fixed, uncommitted)
claims:    11 pinned + green (was 8 in v0.1)
tests:     42 core + 11 render Rust unit; tests/oracle: 45 pass + 121 skip + 8 release_only deselected (no connector in env)
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

## Review round 1 (done — uncommitted on disk)

Five findings, all addressed. Files touched (all tracked, none new):

```
docs/conventions.md                       # P2: tip-angle formula sign
packages/treescape/src/treescape/plot.py  # P1: circular opts; P2: chained-options bug
tests/oracle/test_text_width.py           # P2: importorskip guard
treescape-connector/src/py_render.rs      # getters for label_offset/stroke_width on both PyO3 option classes
treescape-render/src/lib.rs               # P1: render_circular honors start_angle/sweep_total
```

Findings, in the order the reviewer raised them:

1. **P1** `treescape-render/src/lib.rs:39` — `render_circular` and `build_circular_scene_` called `circular_layout(tree)` (defaults), so `CircularSceneOptions(sweep_total=π)` rendered a full circle. Fixed by switching both to `circular_layout_with(tree, opts.start_angle, opts.sweep_total)`. Default behavior unchanged.
2. **P1** `packages/treescape/src/treescape/plot.py:114` — `TreePlot.options(...)` only updated `_scene_opts`; `_circular_opts` was never touched, so `.layout("circular").options(font_size=24)` was a silent no-op. Fixed: `.options()` now updates both, mapping `px_per_x → px_per_r` (per the convention that both axes carry cumulative branch length); `start_angle`/`sweep_total` preserved across reconstruction.
3. **P2** `docs/conventions.md:59` — tip formula was written `θ_i = start_angle + (i / N) · sweep_total` while implementation, tests, and the note at `:64` use `−` for clockwise sweep. Fixed the sign and added a forward pointer to *Sweep direction* so the minus sign isn't a surprise.
4. **P2** `tests/oracle/test_text_width.py:25` — hard-imported `treescape_connector`, so `pytest -q tests/oracle` failed at collection in a checkout without `pip install -e ./treescape-connector`. Wrapped in `try/except ImportError → HAVE_CONNECTOR` and `@pytest.mark.skipif`, matching the pattern in `test_styling_determinism.py` / `test_svg_determinism.py`.
5. **P2 (round-2 follow-up)** `packages/treescape/src/treescape/plot.py:141, 161` — after fix #2 landed, `.options()` still reconstructed both option structs with hardcoded `label_offset=4.0` / `stroke_width=1.0`, so chained calls like `.options(label_offset=12).options(font_size=18)` clobbered the first override. Fixed by adding `#[getter]` for `label_offset` and `stroke_width` to `PySceneOptions` and `PyCircularSceneOptions`, then reading from the existing struct in Python instead of hardcoding.

Verification at the end of round 2:

```
cargo build --workspace                      ✓
cargo test --workspace                       ✓ (42 core + 11 render)
pytest -q tests/oracle -m "not release_only" ✓ (45 pass, 121 skip, 8 deselected)
```

Reviewer's parting note after round 2: "The previous four findings are addressed."

## Two next steps before tagging v0.2.0

```bash
# 1. Commit the uncommitted review fixes. Two commits feels right:
#    one for the P1s (lib.rs + plot.py circular path) and one for the
#    P2s (docs sign, importorskip, getters + chained-options fix).
#    Or one bundled "review round 1 fixes" — judgment call.
git status   # five tracked files modified, no untracked
git diff --stat

# 2. Optional: a second external review pass on the round-1 diff —
#    the cadence memory's recurring findings (claim overstatement,
#    undeclared test deps, silent tolerance bumps) are not the
#    failure mode this round caught, so a fresh pair of eyes might
#    spot a different class. Skip if you trust the closure note.

# 3. Tag.
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
