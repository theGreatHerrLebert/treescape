# Changelog

All notable changes to treescape are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2026-04-28

### Fixes (review round 1, post-phase-3)

- **`render_circular` honors `CircularSceneOptions.start_angle` / `sweep_total`.** Previously both `treescape_render::render_circular` and `build_circular_scene_` called `circular_layout(tree)` with hardcoded defaults, so a fan request via the connector (`CircularSceneOptions(sweep_total=π)`) silently rendered a full circle. Both now route through `circular_layout_with(tree, opts.start_angle, opts.sweep_total)`. Default behavior unchanged.
- **`TreePlot.options(...)` now updates the circular option struct.** It previously only mutated `_scene_opts`, so `.layout("circular").options(font_size=24, padding=…)` was a silent no-op on the circular render path. Shared knobs (`padding`, `font_size`, `label_offset`, `stroke_width`) and `px_per_x → px_per_r` are applied to both option structs; `start_angle` / `sweep_total` are preserved across reconstruction.
- **Chained `.options()` calls preserve prior overrides.** The reconstruction step previously hardcoded `label_offset=4.0` and `stroke_width=1.0`, so `.options(label_offset=12).options(font_size=18)` reset `label_offset` back to default. Added `#[getter]` for `label_offset` and `stroke_width` on `PySceneOptions` and `PyCircularSceneOptions`; Python now reads from the existing struct instead of hardcoding.
- **`docs/conventions.md` tip-angle formula sign.** The body wrote `θ_i = start_angle + (i / N) · sweep_total` while implementation, tests, and the note immediately below it use `−` to encode the clockwise sweep. Sign corrected; forward pointer to *Sweep direction* added so the minus sign isn't a surprise.
- **`tests/oracle/test_text_width.py` no longer fails collection without the connector.** Hard `from treescape_connector.py_render import …` replaced with `try/except ImportError → @pytest.mark.skipif`, matching `test_styling_determinism.py` / `test_svg_determinism.py`.

### Phase 3 — clade highlighting + per-tip color overrides

- **`TreePlot.highlight_clade(tips=[...], color=, alpha=)`** — chainable. The MRCA of the named tips is computed and a translucent rectangle is drawn behind branches and labels, spanning from the MRCA's branch point to the canvas right edge, covering all rows in the clade.
- **`TreePlot.color_tips({name: color, ...})`** — chainable. Overrides per-tip label color; tips not in the map keep `SceneOptions.label_color`.
- Color specs accept `"#rrggbb"`, `"#rrggbbaa"`, `(r, g, b)`, or `(r, g, b, a)` (0–255 ints). Validated up front by `_parse_color`.
- **New EVIDENT claim** `treescape-styling-determinism` (ci-tier, property-style): same input + same styling → byte-identical SVG, across 4 fixtures × 3 modes (repeated render, golden snapshot, Rust↔Python ref bytes) = 12 tests.
- New scene types: `Rect(x, y, width, height, fill)` in both Python and Rust, emitted as `<rect>` before lines/arcs/text so highlights render behind branches.
- New helpers: `find_mrca(tree, tip_names)` and `clade_tips(tree, mrca)` in both `treescape-reference` and `treescape-core`. Mismatched / missing tip names raise cleanly.
- Rust scene builder: `build_rectangular_scene_with_style(...)` extends `..._with_measurer` with a `&StyleSpec` parameter; the previously-public `_with_measurer` now delegates with an empty `StyleSpec` so existing rectangular SVG bytes are unchanged.
- Python ref: `build_rectangular_scene(tree, opts, measure, style=None)` — same shape, default `None` style preserves prior bytes.
- Connector: new `render_rectangular_styled_svg(tree, opts, highlights, tip_colors)` PyO3 function.
- **Cuts deferred to v0.3:** circular layout + clade highlighting (raises `NotImplementedError` cleanly); metadata-driven color (`color_branches_by(metadata_col=...)` requires the `join_metadata` API which is a separate v0.2 deliverable); branch-color overrides; node shape styling.

### Phase 2 — circular layout (part 2: rendering + oracles)

- **Circular SVG rendering.** New `Arc` scene-graph item (Python + Rust) emitted as SVG `<path d="M ... A r r 0 large sweep ...">`; new `rotation_deg` field on `Text` emitted as `transform="rotate(...)"`. The circular scene builder combines radial branch lines, arc spines (one per internal node with ≥2 children, at radius=parent.r), and rotated tip labels with hemisphere-flipped anchor so labels read outward.
- **`TreePlot.layout("circular")`** is now a supported user-facing layout. `treescape_connector.py_render` exposes `CircularSceneOptions` and `render_circular_svg`.
- **`treescape-svg-determinism`** claim extended to circular: 12 new tests across 4 fixtures × {repeated, golden snapshot, Rust↔Python ref bytes}. Goldens checked in at `tests/fixtures/golden/<fixture>_circular.svg`.
- **`treescape-circular-layout-vs-ete3`** (ci-tier) — green. ete3 doesn't expose circular coords (Qt-bound); same indirect strategy as the rectangular ete3 oracle works here too: r ↔ `ete3.get_distance`, θ derived from ete3's `iter_leaves()` pre-order index applied to treescape's convention formula.
- **`treescape-circular-layout-vs-ggtree`** (release-tier) — green. As predicted, the first end-to-end run surfaced two real divergences (documented in `docs/conventions.md`):
  - ggtree's tip *i* (1-based) sits at `i·2π/N` sweeping **CCW**, last tip at 3 o'clock. treescape uses `π/2 − i·2π/N` sweeping **CW**, first tip at 12 o'clock. Per-tip transform: `θ_ggtree = 2π/N + π/2 − θ_ours` (mod 2π).
  - ggtree uses linear mean for internal-node angle; treescape uses wrap-aware vector mean. Diverges only on diametrically-opposed children. Oracle test sidesteps by comparing tips only.
- `workflow/scripts/oracle_ggtree.R` gains a `--circular` flag that emits `(node, r, θ)` for the new oracle test.

### Phase 2 — circular layout (part 1: coordinates)

- **`circular_layout(tree)`** in `treescape-reference` and `treescape-core` — polar `(r, θ)` per node. `r` is cumulative branch length (matching rectangular's x); tip θ is `start_angle − (i / N) · sweep_total` for tip `i` in pre-order leaf traversal — clockwise from `start_angle`. Internal-node θ uses the wrap-aware vector mean (`atan2` of summed unit vectors) so children straddling the 0/2π boundary still produce a sane bisector.
- **Defaults:** `start_angle = π/2` (12 o'clock), `sweep_total = 2π` (full circle). Configurable for fan layouts (`sweep_total = π` etc).
- **Two new EVIDENT claims** pinned: `treescape-circular-layout-vs-ete3` (ci) and `treescape-circular-layout-vs-ggtree` (release). Oracle tests land in part 2 alongside the rendering. Per the v0.1 cadence, claims pinned before code.
- **Rust↔Python parity** under `treescape-layout-rust-vs-reference` extends to circular: 4 fixtures × `(r, θ)` per tip within `1e-9`.
- **Convention doc:** `docs/conventions.md` gains a "treescape conventions (v0.2, circular layout)" section locking radius rule, tip-θ formula, internal-node arc-aware mean, and the SVG y-flip Cartesian projection.
- **TreePlot.layout("circular")** still raises `NotImplementedError` — user-facing rendering lands in part 2.

### Phase 1 — fontdue tip-label widths

- **Real glyph metrics for tip-label widths.** v0.1 estimated label width as `N_chars * font_size * 0.6` (a monospace approximation that was wrong for proportional fonts). v0.2 replaces it with fontdue advance-width measurement of the bundled DejaVu Sans on the Rust side and `fontTools` HMTX read on the Python reference side. Both produce floating-point-identical widths across the test battery.
- **New EVIDENT claim** `treescape-text-width-vs-fontdue` (ci-tier): Rust widths agree with the Python reference within 0.5 px on a 14-string × 5-size battery (70 cases).
- **API change:** `SceneOptions(avg_glyph_width=...)` is no longer accepted by the Python API; the Rust `CoreSceneOptions.avg_glyph_width` field is retained for the legacy `build_rectangular_scene` (no-measurer) fallback only. The user-facing `treescape-render` and PyO3 paths use fontdue unconditionally.
- **Canvas widths shifted.** All four golden SVG fixtures and `assets/primates.svg` regenerated; byte-determinism still holds across runs.
- **`scripts/regen_assets.py`** added — canonical `assets/primates.svg` regeneration.
- **`fonttools>=4.50`** added to `treescape-reference` runtime deps.
- The bundled `DejaVuSans.ttf` is now shipped in both `treescape-render/src/fonts/` and `packages/treescape-reference/src/treescape_reference/fonts/` so the Python wheel is self-contained.

## [0.1.0] — 2026-04-28

The first shippable cut. Tight v0.1 scope: load Newick, render a rectangular phylogram with tip labels, save deterministic SVG.

### Added

- **Newick parsing/writing** in `treescape-core` (hand-rolled, iterative). Handles quoted names, NHX comments (consumed in v0.1), negative branch lengths, and trifurcation roots. Strict grammar: requires trailing `;`, rejects multiple top-level roots, rejects trailing content after the semicolon.
- **Rectangular layout** with documented conventions (x = cumulative branch length, tip y = pre-order leaf index, internal y = mean of immediate children's y).
- **Ladderization** with both ascending and descending orders. The descending tie-break matches ete3's `direction=1` behavior exactly (sort key `(-size, -original_position)`).
- **Pure-Rust deterministic SVG renderer** in `treescape-render`. Sorted attributes, fixed `{:.4}` float formatting, no timestamps. Bundles DejaVu Sans for downstream font measurement.
- **PyO3 bindings** in `treescape-connector` mirroring the rustims layout (one cdylib, four `wrap_pymodule!` submodules registered in `sys.modules`).
- **`TreePlot` grammar** in the user-facing `treescape` Python package. v0.1 surface is intentionally tight: load, layout, tips, options, save.
- **`treescape-reference` Python package** — slow, readable parser/layout/renderer that serves as the EVIDENT oracle for the Rust core. Designed to be PyPI-publishable so users can verify claims independently.
- **EVIDENT trust manifest** at `evident.yaml` with eight claims pinned before implementation:
  - `treescape-newick-roundtrip` (ci): Biopython parity + own-roundtrip
  - `treescape-layout-rust-vs-reference` (ci): Rust matches Python reference within `1e-9`
  - `treescape-layout-vs-ete3` (ci): ete3 traversal + distance parity within `1e-6`
  - `treescape-layout-vs-biopython` (ci): Biopython.Phylo.draw layout parity within `1e-6` (Biopython's own functions extracted via `inspect`)
  - `treescape-layout-vs-ggtree` (release): R + ggtree parity within `1e-4`
  - `treescape-ladderize-order` (ci): tip order matches ete3 `direction=0` and `direction=1`
  - `treescape-svg-determinism` (ci): byte-identical output across runs; Rust↔Python reference byte parity
  - `treescape-tip-count-invariant` (ci): hypothesis property — N tips → N tip glyphs, all coords within canvas

### Trust contract

Claim runners live at `tests/oracle/test_*.py`. The release-tier `ggtree` runner is gated to the image at `workflow/Dockerfile.evident-release` and runs in CI only on tag pushes.

### Known v0.1 limitations (deferred to v0.2)

- Circular and radial layouts.
- PDF export (SVG only).
- Clade highlighting.
- Branch- and node-style mappings to metadata. v0.1 supports `tips(label="name")` only.
- Real fontdue-measured tip-label widths. v0.1 uses `avg_glyph_width=0.6` monospace approximation, sufficient for canvas-bounds invariant but not for aggressive collision avoidance.
- Nexus and PhyloXML parsers.
- `treescape-cli` and a `treeplot` console entry point.
- Polars/pandas dual-support; the metadata API is v0.2.

### Bundled font

DejaVu Sans (Bitstream Vera Fonts License) is bundled at `treescape-render/src/fonts/DejaVuSans.ttf`. License notice alongside.
