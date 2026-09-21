# v0.5 plan

Working plan for the next minor version. Same cadence as v0.1–v0.4: tight scope, EVIDENT claims pinned **before** the code, Python reference first then Rust port, external review at the end of each phase.

## Theme

**A second host language.** rustims ships Rust core + PyO3 connector + Python package **and** a C-ABI connector + Julia package (`imsjl_connector/` + `IMSJL/`). v0.5 gives treescape the same shape: `treescape-jl-connector` (C ABI cdylib) + `Treescape.jl`, and a docs page with side-by-side Python and Julia examples.

The blocker is not the FFI. It is that **~450 of `plot.py`'s 789 lines are styling *resolution* logic living in Python**: palette assignment, pinned viridis LUT, value normalization, the monophyly rule, subtree means, width scaling. Rust only ever sees final per-node colors/widths (`render_*_styled_svg`). A Julia binding written today would have to re-implement all of that in Julia — a second copy of the conventions, with its own drift risk and no oracle. So Phase 1 moves resolution into Rust, Phase 2 builds the Julia binding on top of it, Phase 3 documents both.

## Julia landscape (why this is worth doing)

Checked against the General registry, 2026-09-21:

- **Phylo.jl** (EcoJulia, 0.5.x) — Plots.jl recipes, rectangular + fan. Closest competitor.
- **PhyloPlots.jl** (JuliaPhylo, 2.x) — for PhyloNetworks; plots via RCall (R graphics). Network-oriented.
- **NewickTree.jl**, **PhyloTrees.jl** — minimal RecipesBase recipes.

None offers byte-deterministic SVG, metadata-driven discrete/continuous styling, annular clade highlights, or layout coordinates held to ete3/Biopython/ggtree. `Treescape.jl` fills a real gap rather than duplicating one.

## Proposed trio (in implementation order)

### Phase 1 — move styling resolution from `plot.py` into Rust

Behavior-preserving refactor. **Zero SVG bytes change** is the acceptance bar: every golden under `tests/fixtures/golden/` and every file in `assets/gallery/` must be byte-identical before and after.

Reference-first, per cadence:

1. **Extract** the resolution functions from `plot.py` (adapted to the Rust boundary shape) into `packages/treescape-reference/src/treescape_reference/style.py` (`parse_color`, `TABLEAU_10`, `VIRIDIS_LUT`, `viridis`, `normalize`, `value_range`, `resolve_discrete_palette`, `discrete_branch_colors`, `continuous_branch_values`, `branch_widths`). `plot.py` temporarily calls the reference module; goldens must still pass. This pins the oracle **before** Rust exists.
2. **Port** to `treescape-core::style` (pure Rust, no PyO3).
3. **Rewire** `plot.py` to call the Rust resolver through a new `py_style` submodule (`wrap_pymodule!`, alongside `py_tree`/`py_layout`/`py_render`/`py_metadata`).

What moves, what stays host-side:

| Concern | Where | Why |
|---|---|---|
| Tableau-10, viridis LUT | Rust | pinned conventions; must be identical in every host |
| normalize (incl. `hi <= lo → 0.5`), clamp, value range | Rust | same |
| monophyly rule, subtree mean, width scaling, terminal-branch rule | Rust | same |
| dataframe handling (polars / Tables.jl) and join-key validation | host | host-native types; join keys may be non-strings (a polars `Int64` key must fail with the v0.3 "not a tree tip" error, not an FFI type error). *Revised during Phase 1 — originally planned for Rust.* |
| color *input* parsing (`"#rrggbb"`, tuples) | host | hosts have idiomatic color types; palette entries must be parsed lazily exactly where v0.4 did. *Revised during Phase 1 — originally planned for Rust.* |
| numeric-vs-discrete dtype detection | host | host type systems differ (Python `bool` is excluded from numeric; Julia `Bool <: Integer`) — pinned per host in `docs/conventions.md` |
| user-callable `cmap` | host | Rust returns per-node `t ∈ [0,1]`; built-in `"viridis"` maps in Rust, a callable maps in the host |
| emitting `TreescapeStyleWarning` | host | Rust returns non-monophyletic node ids; host formats the (unchanged) message and warns. Keeps the round-3 `simplefilter("error")` atomicity fix intact |

Boundary shape: columns cross as tip-order-aligned vectors — numeric as `Vec<Option<f64>>`, discrete as `Vec<Option<u32>>` codes (first-seen order in tip order, matching today's palette assignment) plus a code→color table. No row dicts cross FFI.

**Byte-parity traps to pin in `docs/conventions.md` before porting** (these are exactly where a naive port silently diverges):

- **Rounding.** `_viridis` uses Python `round()`, which is **round-half-to-even**. Rust `f64::round` is half-away-from-zero. Port must use `f64::round_ties_even`. Include a fixture that hits an exact `.5` channel value.
- **Summation algorithm.** Subtree means sum in `_descendant_tips` order (left-to-right preorder) with builtin `sum()` — which since **Python 3.12 is Neumaier-compensated**, not a sequential fold (`sum([1e16, 1.0, -1e16])` is `0.0` on 3.11, `1.0` on 3.12). treescape supports ≥ 3.11, so v0.4 output was already interpreter-dependent; goldens came from 3.12. Pin the 3.12 algorithm explicitly in both the reference and Rust. *(Found during Phase 1; the first draft of this plan said "sequential fold".)*
- **NaN.** Python `min()`/`max()` with NaN are order-dependent, and `int(round(nan))` raises `cannot convert float NaN to integer`; replicate both.
- **Float→int.** `int(round(x))` on the interpolated channel; no truncation shortcuts.

**EVIDENT:**
- New claim `treescape-style-resolution-rust-vs-reference` (ci-tier): for every styling fixture (discrete/continuous × tips/branches × widths, both layouts, incl. the `.5`-rounding and degenerate-range fixtures), the Rust resolver's output maps are **exactly equal** (no tolerance — ints and the same f64 bits) to `treescape_reference.style`.
- Existing `treescape-svg-determinism`, `treescape-styling-determinism`, `treescape-color-*`, `treescape-branch-width-*`, `treescape-circular-annotation-determinism` goldens: unchanged bytes. Any golden regen in Phase 1 is a bug, not an update.

### Phase 2 — `treescape-jl-connector` + `Treescape.jl`

Mirrors rustims' `imsjl_connector` / `IMSJL`, with three deliberate improvements over it.

**Rust side — `treescape-jl-connector/`** (workspace member, `crate-type = ["cdylib"]`, lib name `treescape_jl_connector`):

- Opaque handles: `TsTree`, `TsStyle` (builder), `TsSceneOptions`, `TsCircularSceneOptions`. Each has `_new`/`_free`.
- Every fallible entry point returns an `i32` status and writes an out-pointer plus an optional `*mut c_char` error message (`ts_string_free` releases it). Example: `ts_tree_parse_newick(src, &out_tree, &out_err) -> i32`.
- Style builder calls mirror Phase 1's resolver inputs (numeric/discrete columns as pointer+length arrays), render calls return an owned SVG `*mut c_char`.

**Improvement 1 — no panics across the FFI.** The workspace release profile sets `panic = "abort"` (and it cannot be overridden per package), so `catch_unwind` is useless: any panic — an `unwrap()` on a malformed Newick string, an out-of-range node id — **kills the host Julia process**. rustims' `imsjl_connector` has this bug (`CStr::to_str().unwrap()`). Treescape's connector:
  - `#![deny(clippy::unwrap_used, clippy::expect_used, clippy::panic, clippy::indexing_slicing)]` at crate root.
  - Null-pointer and UTF-8 checks on every input → error status.
  - An audit of `unwrap`/`expect`/indexing on the `treescape-core`/`treescape-render` paths reachable from the connector; convert to `Result` where the input is user-controlled.

**Improvement 2 — library discovery.** No hardcoded `target/release/*.so` path. Order: `ENV["TREESCAPE_JL_LIB"]` → Preferences.jl `libpath` → dev fallback `<repo>/target/release/libtreescape_jl_connector.{so,dylib}`. A BinaryBuilder/Yggdrasil JLL is **out of scope** for v0.5 (see below).

**Improvement 3 — finalizers.** Julia wrapper types own their handle and register `finalizer(ts_*_free, obj)`; no manual `destroy` calls in user code.

**Julia side — `packages/Treescape.jl/`**:

- `Project.toml` compat `julia = "1.10"`; developed and CI-tested on **1.12** (local: `~/julia/julia-1.12.7/bin/julia`; bare `julia` on PATH is 1.10).
- Deps: `Tables.jl` (metadata accepts any Tables.jl source — DataFrames, CSV.File, NamedTuple-of-vectors) and `Preferences.jl` (library path). No Plots/Makie dependency.
- API: Julian bang-mutators that return the plot, keyword names identical to Python:

  ```julia
  using Treescape, DataFrames

  p = TreePlot("primates.nwk")
  layout!(p, :circular)
  join_metadata!(p, df; on = :tip)
  color_tips_by!(p, :clade)
  scale_bar!(p, 0.05, "0.05 subs/site")
  save(p, "primates_circular.svg")
  ```

- `Base.show(io, ::MIME"image/svg+xml", p)` → inline display in Pluto, Jupyter (IJulia), VS Code for free.
- `TreescapeStyleWarning` → `@warn` with a `_group = :treescape_style` tag.

**EVIDENT:**
- New claim `treescape-julia-python-svg-parity` (ci-tier): for all 13 gallery configurations plus the styling-determinism fixtures, `Treescape.jl` output is **byte-identical** to `treescape` (Python) output. Claim text must state plainly what this is: a **binding-fidelity** claim (both hosts drive the same Rust core), *not* independent evidence of layout correctness — that evidence remains the ete3/Biopython/ggtree oracles. (Pre-empts the recurring "claim overstatement" review finding.)
- New claim `treescape-jl-ffi-no-abort` (ci-tier, property-style): malformed Newick, null/invalid-UTF-8 inputs, out-of-range node ids, empty columns, mismatched column lengths → error status + message, and the Julia process survives. Runner spawns a Julia subprocess per case so an abort shows up as a failure rather than taking down the harness.
- CI: new `julia` job (`julia-actions/setup-julia@v2` with `version: '1.12'`, plus `'1.10'` as compat floor), builds the connector, runs `Pkg.test("Treescape")` and the parity runner. Julia added to `workflow/Dockerfile.evident-release` so release-tier runs include it.

### Phase 3 — docs site (GitHub Pages) with Python + Julia examples

- **GitHub Pages site** built from `docs/` and deployed by a CI workflow on push to `main` (and on tags): use cases (`cases/`), the examples page, `docs/conventions.md`, the EVIDENT claim table rendered from `evident.yaml`, and the gallery. Generator: MkDocs-Material (locked 2026-09-21). Enabling Pages in the repo settings is a one-time user action.

- `docs/examples.md`: 6–8 examples on the primates fixture, each shown as a Python block and a Julia block producing the **same SVG** (embedded from `assets/gallery/`):
  1. Minimal rectangular render
  2. Circular layout
  3. Clade highlight
  4. Discrete tip + branch color from a joined table
  5. Continuous (viridis) coloring by support
  6. Branch width by support
  7. Scale bar + support labels
  8. Publication-style combination (gallery 10)
- **Docs don't rot:** a test (`tests/docs/test_examples.py` + `packages/Treescape.jl/test/docs_examples.jl`) extracts every fenced block from `docs/examples.md`, executes it, and asserts the output bytes equal the referenced gallery SVG. Covered by `treescape-julia-python-svg-parity`'s coverage table (no new claim ID — same precedent as v0.4 extending existing claims).
- README: fix the stale "v0.3.0 shipped" status line, add the Julia row to *Quick architecture*, link `docs/examples.md`.
- Gallery README: add a Julia column next to the Python code column.

## Explicitly NOT in v0.5

- **JLL / General-registry registration** of `Treescape.jl`. Needs BinaryBuilder recipe in Yggdrasil, cross-compiled artifacts, a stable C ABI. v0.6 once the ABI has survived a minor.
- **Plots.jl / Makie recipes.** `show(::MIME"image/svg+xml")` covers notebook display; a Makie backend would be a second renderer and break the single-emitter determinism story.
- **Phylo.jl interop** (`TreePlot(::Phylo.AbstractTree)`). Nice, but adds a heavy dep; Newick round-trip covers it for now.
- **Phylo.jl as a 4th independent layout oracle.** Genuinely interesting (independent Julia lineage), but its coordinates live inside a Plots recipe; extracting them is its own investigation. Candidate for v0.6.
- **Sub-quadratic branch styling.** Found in Phase 2 review: O(nodes × depth) on ladder trees. A faster algorithm must preserve the pinned summation order; v0.6.
- **Moving `join_metadata` value storage into Rust / Arrow FFI.** Only key validation moves in Phase 1; columnar FFI waits for a >50k-tip use case (same deferral as v0.4).
- Everything still deferred from v0.4 (PDF, Nexus/PhyloXML, node markers, CLI, label collision, unrooted layout).

## Cadence (same as v0.1–v0.4)

For each phase:

1. Lock convention decisions in `docs/conventions.md` **before** any code.
2. Pin EVIDENT claim in `evident.yaml` **before** the test exists.
3. Python reference first (`treescape-reference`).
4. Rust port held to the reference (Phase 1: exact equality).
5. Wire through connectors (PyO3 in Phase 1; C ABI + Julia in Phase 2).
6. External review at end of phase; close findings before the next phase. Watch the recurring ones: claim overstatement, undeclared test deps (Julia is a new one — the parity tests must skip cleanly with a clear reason when Julia or the jl connector is absent, never silently pass), silent tolerance bumps.
7. Commit + push per phase milestone.

## Decisions (locked 2026-09-21)

1. **Julia package location:** `packages/Treescape.jl/` (consistent with CLAUDE.md's `packages/` rule; rustims' root-level `IMSJL/` not mirrored here).
2. **Julia API style:** bang-mutators returning the plot (`color_tips_by!(p, :clade)`). No curried/pipe forms in v0.5.
3. **Julia CI matrix:** `1.12` + `1.10` (compat floor `julia = "1.10"`).
4. ~~Phase 1 ships standalone as v0.4.1~~ — revised 2026-09-21: no v0.4.1 tag; Phase 1 is logged in the v0.5.0 CHANGELOG and **v0.5.0 is tagged after Phase 3**.
5. **Docs site generator: MkDocs (Material theme)** for the whole site; the Julia API is documented in `packages/Treescape.jl/README.md`, linked from the site (no Documenter.jl in v0.5).

## Success criteria

v0.5 ships when:

- All three phases landed on main (one commit per phase).
- 21 EVIDENT claims green (18 from v0.4 + `treescape-style-resolution-rust-vs-reference`, `treescape-julia-python-svg-parity`, `treescape-jl-ffi-no-abort`).
- **Zero golden regeneration** across the whole minor — v0.4 SVG bytes are preserved for every fixture and gallery file.
- `plot.py` contains no palette/LUT/normalize/monophyly/mean logic; grep for `_VIRIDIS_LUT` / `_TABLEAU_10` in `packages/treescape` returns nothing.
- `treescape-jl-connector` builds with the clippy deny-list above and zero `unwrap`/`expect` on FFI-reachable paths.
- CI green: Rust, ci-tier Python, new Julia job; release-tier on the v0.5.0 tag.
- `docs/examples.md` published with every Python and Julia block executed in CI.
- External review of all three phases closed; CHANGELOG updated; tag `v0.5.0` pushed.
