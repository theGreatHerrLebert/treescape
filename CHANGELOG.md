# Changelog

All notable changes to treescape are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — v0.6.0

### Changed — v0.6 Phase 1: EVIDENT schema migration

- `evident.yaml` follows the upstream EVIDENT schema (submodule `bf990d2` → `bd79f68`): `project`, `vocabularies` (subsystems, oracles, a `mismatch_count` metric), and per claim `subsystem`, `inputs` (named corpus, count, class, `corpus_sha`), `pinned_versions` and structured `tolerances` (`metric`/`op`/`value` = the comparison the runner asserts; `prose` = the old tolerance text). Structural only: every claim's text, command and artifact is unchanged, and all 21 claims keep their ids. Both upstream gates pass: `validate_manifest.py --strict-release-pins` and `typed-trust`.
- **Oracle versions are pinned** (`tests/requirements-oracles.txt`, used by CI and the release image; Bioconductor pinned to 3.22 in the image). Before, every environment installed the latest: the release image had Biopython 1.88 while local runs used 1.87.
- New `tests/oracle/test_manifest.py`: the `treescape` pin equals the workspace version, each Python oracle pin equals the installed version, each `corpus_sha` equals the hash of the files in `tests/fixtures/corpora.toml` (`scripts/corpus_sha.py`), and (release tier) the ggtree pin equals the image's.
- CI validates the manifest with the upstream tools; treescape's copy of the old-schema validator (`workflow/validate_manifest.py`, `workflow/Dockerfile.evident-base`) is removed. `evident/` is excluded from the Cargo workspace so `typed-trust` builds in place.
- Docs: the claims page shows subsystem, pinned oracles, structured tolerances and input corpora; the EVIDENT **claim viewer** (`typed-trust --format site`: filterable claims table, subsystem × tier coverage, claim–oracle graph) is published at `/trust/`.

- Phase 1 review fixes:
  - The Rust Newick round-trip now compares branch lengths and names. The topology hash covers neither, so the claim's "branch lengths" was only tested for the Python reference.
  - Structured fields now also encode the runners' non-exact assertions (sector angles `< 1e-12`, annotation geometry `< 1e-9`).
  - `hypothesis` and the Python version are pinned for the style-resolution claim.
  - The parity and style-resolution inputs are hashed corpora. `primates.nwk` and the gallery were previously outside any hash.
  - Miri is no longer listed as an oracle of a command that does not run it.
  - The manifest test requires every oracle to have a pin check, and every fixture claim to name a hashed corpus.

### Changed — v0.6 Phase 2: layout oracles on real and random trees, against the Rust code

- **Pinned random corpus:** `scripts/gen_random_trees.py` (seeded; rules in `docs/conventions.md`) writes 60 trees to `tests/fixtures/trees/random/`: yule, pda, ladder, polytomy and zero-length shapes, from 3 to 200 tips. Together with the small and edge layout fixtures and `primates.nwk`, and a hand-written tree with an evenly spread inner node (`edge/evenly_spread_inner.nwk`), they form the hashed `layout-v2` corpus (66 trees). A test fails if the files and the generator disagree.
- **External oracles now check the Rust core, not only the Python reference.** The ete3, Biopython and ggtree runners (rectangular and circular) compare both implementations on every tree of `layout-v2`. Before, they compared `treescape-reference` on 4 trees of 2–5 tips. The README, docs home page and trust case say so.
- **Every node, not only tips**, wherever the oracle defines it: Rust↔reference on every node of both layouts; ete3 x of every node; Biopython x of every node and y of every two-child node; ggtree x and y of every node (rectangular) and r of every node (circular). Nodes are matched by clade (`tests/oracle/_layouts.py`). `workflow/scripts/oracle_ggtree.R` now also prints each node's parent.
- The six layout claims now name the new corpus and say which implementation each oracle checks. Tolerances are unchanged.
- The macOS arm64 CI job runs the byte-determinism, golden and gallery runners against the same goldens.

### Added — v0.6 Phase 3: trees from distance matrices

- **Neighbor joining and UPGMA**: `TreePlot.from_distances(D, labels, method="nj"|"upgma")` and `TreePlot.from_linkage(Z, labels)` (SciPy linkage matrices) in Python; `TreePlot(D, labels; method = :nj)` in Julia; `to_newick` in both. Built in `treescape-core::tree_build` (reference first: `treescape_reference.tree_build`). Everything else works on the result unchanged: circular layout, metadata, styling, scale bars.
- **Conventions** (`docs/conventions.md`, "Trees from distance matrices"): the Studier–Keppler NJ criterion, the NJ root at the last three-way join, negative lengths kept, size-weighted UPGMA, a pinned tie rule (first pair in list order) and summation order, and input checks that name the offending cell. Rust and the reference build bit-identical trees, ties included.
- **Seven claims**:
  - `treescape-tree-build-rust-vs-reference`: every tie included.
  - `treescape-nj-vs-oracles`: scikit-bio `nj` with `neg_as_zero=False`, and Biopython.
  - `treescape-nj-vs-ape` (release).
  - `treescape-upgma-vs-scipy`.
  - `treescape-upgma-vs-phangorn` (release).
  - `treescape-nj-recovers-additive-trees`: ground truth rather than another implementation.
  - `treescape-tree-build-performance`: bounded time ratios; see below.

  The oracle claims run on 72 generated matrices (`distance-v1`: additive and noisy matrices from the pinned random trees), and every matrix is first proven tie-free. The oracles break ties differently, so tie behaviour is covered by the Rust↔reference claim and three hand-written tie fixtures.
- **Oracle findings**, documented rather than absorbed:
  - Biopython's `DistanceTreeConstructor.upgma` computes **WPGMA** (unweighted cluster average), so it is not used as a UPGMA oracle.
  - scikit-bio's `upgma` wraps SciPy, so it would not be independent.
  - scikit-bio's `nj` clamps negative lengths by default.
- **Performance, measured and stated honestly** (`docs/performance.md`): exact O(n³) NJ is 2.0–3.7× slower than scikit-bio's optimized `nj` at 500–2000 taxa and about 1,000× faster than Biopython's. UPGMA, with cached row minima, is 2.4–3.7× slower than SciPy. The claim bounds these ratios. It does not say "fast". The three optimizations kept (a compacted active-order matrix, overlapped row totals, cached UPGMA row minima) change no result: the parity claims prove it. Faster NJ is v0.7 work.
- **C ABI 2**: `ts_tree_from_distances`, `ts_tree_from_linkage`, `ts_tree_write_newick` (input capped at 10,000 taxa; the no-abort runner covers the new entry points: 1,611 cases).
- **Release image**: phangorn (plus the `libglpk40` its igraph dependency needs, found because phangorn failed to load); every oracle package is loaded once at build time. Release-tier runners now **fail instead of skipping** when a tool is missing (`TREESCAPE_REQUIRE_RELEASE=1` in the image): the first run with phangorn had skipped 288 tests and still reported success.
- Code review: `from_linkage` (Rust and reference) now rejects a linkage matrix that joins a cluster twice, which would have dropped or duplicated tips, and checks labels like `from_distances` does. A Rust↔reference parity test for `from_linkage` covers all 72 corpus matrices.
- Gallery 14 and 15 and two tested examples (Python and Julia, byte-identical): the standard NJ teaching matrix built with NJ and with UPGMA.

### Fixed — found by v0.6 Phase 2 node-level comparison

- **Circular layout: a node whose children are spread evenly got a rounding-noise angle.** The wrap-aware mean of the children's unit vectors is the origin when they are spread evenly. Examples: a star root such as `(a,b,c);`, the two opposite children of a two-tip tree, and a drawn inner node whose arc exceeds π, such as `(b,(c,d,e),f)` in `(a,(b,(c,d,e),f));`. `atan2` then returned noise, and that noise differed between the Rust core and the Python reference. The reference also summed with Python's compensated `sum()` (Neumaier on 3.12+, naive on 3.11) instead of Rust's left-to-right fold.
  - Both implementations now sum left to right.
  - A sum with norm below 1e-9 now gives the node the midpoint of its own tip arc (`docs/conventions.md`), which keeps inner nodes on their descendants' side.
  - Every golden and gallery SVG is byte-identical: none contains such an inner node, and a root's angle is not drawn.
  - v0.5's tip-only comparisons could not see this. The Phase 2 runners compare every node, and an independent review then found the inner-node case, which the first version of this fix got wrong.

### Noted, not changed (needs a decision)

- `treescape-circular-layout-vs-ete3` claims 1e-4, but its runner asserts `< 1e-6`. The claim understates its own evidence.
- *Resolved by Phase 2:* the layout claims' "small and medium fixtures" wording (they now name `layout-v2`, which includes the medium fixture); the external-oracle claims testing only the Python reference (they now check both implementations); the two inaccurate ete3 sentences (rewritten). Still open from the same Phase 1 finding: `treescape-tip-count-invariant` (`source: treescape-render`) runs the Python reference renderer only. It moves to the v0.7 render-fidelity work.

## [0.5.0] — 2026-09-21

A second host language. Styling resolution moved from Python into the Rust core (Phase 1), a C-ABI connector and `Treescape.jl` drive that core from Julia with byte-identical output (Phase 2), and a docs site shows every example in both languages (Phase 3). Three EVIDENT claims added (21 in total).

Metadata-driven styling resolution moved from `plot.py` into `treescape-core::style` (exposed as `treescape_connector.py_style`), in preparation for the Julia binding. No API changes. New EVIDENT claim `treescape-style-resolution-rust-vs-reference`.

### Changed — Phase 1: styling resolution in Rust

- **Python 3.11: subtree-mean branch colors and widths now match Python 3.12.** v0.4 averaged subtree values with builtin `sum()`, whose float algorithm changed in Python 3.12 (Neumaier compensation). For cancellation-prone values (e.g. `[1e16, 1.0, -1e16]`) v0.4 produced different colors/widths on 3.11 than on 3.12 and than the committed goldens. v0.5 pins the 3.12 algorithm in Rust, so output is now interpreter-independent. Python 3.12+ output is unchanged: every golden and gallery SVG is byte-identical.

### Added — Phase 1

- `tests/oracle/test_gallery_bytes.py`: every `scripts/regen_assets.py` configuration is rendered in memory and compared byte-for-byte to the committed `assets/` files. `scripts/regen_assets.py` now exposes the configurations as a `GALLERY` list.

### Fixed — Phase 1

- `cargo clippy --workspace -- -D warnings` failed on `main` since v0.4 Phase 3 (`too_many_arguments` on the two `render_*_styled_svg` PyO3 functions); allowed explicitly.

### Added — v0.5 Phase 2: Julia binding

- **`Treescape.jl`** (`packages/Treescape.jl`) — the full TreePlot grammar in Julia (`layout!`, `options!`, `highlight_clade!`, `color_tips!`, `join_metadata!` over any Tables.jl source, `color_tips_by!`, `color_branches_by!`, `width_branches_by!`, `scale_bar!`, `support_labels!`, `to_svg`, `save`, inline SVG display). Julia ≥ 1.10; CI on 1.10 and 1.12.
- **`treescape-jl-connector`** — C-ABI cdylib in the rustims `imsjl_connector` style: opaque handles, status codes with owned error messages, finalizer-managed memory, ABI version check, library discovery via `TREESCAPE_JL_LIB` / Preferences.jl / the dev build. Unlike `imsjl_connector` it cannot panic across the boundary (clippy deny-list on `unwrap`/`expect`/`panic`/indexing; null, alignment and size checks on every pointer). Unit tests call the C functions in-process and run under Miri in CI.
- Claims `treescape-julia-python-svg-parity` (39 data-only cases in `tests/fixtures/parity/cases.toml`, including every gallery file, byte-identical between Julia and Python) and `treescape-jl-ffi-no-abort` (1,601 hostile, fuzzed and oversized inputs through the raw ABI; the Julia process must survive). Both fail rather than skip in the CI `julia` job.

### Fixed — Phase 2 review round 1 (general + FFI robustness reviews)

- **Julia memory safety.** Every `ccall` now passes the owning `Tree` (rooted for the call) instead of its raw pointer, which the GC could otherwise finalize mid-call; `deepcopy`/`copy` share the tree owner instead of duplicating the handle (two finalizers, one handle); the finalizer captures its free-function pointer at construction and never takes a lock; all symbols are resolved once under a lock at load; returned strings are freed in `finally`; a library that fails the ABI check is `dlclose`d.
- **C ABI.** Output destinations are validated before strings are allocated (a rejected call leaked the whole SVG); the `err` pointer is validated before it is written; a non-null options pointer that fails validation is an error rather than a silent fallback to defaults; Rust writes caller buffers with raw copies and never forms `&mut [T]` over possibly-uninitialized Julia memory; Newick input over 16 MiB is rejected before parsing (64 MiB in round 1; lowered in round 2).
- **Invalid SVG from non-finite numbers (Python too).** NaN/infinite options, branch lengths or scale bars — or finite values whose derived geometry overflows (e.g. `font_size=1e300`) — produced `NaN`/`inf` attributes. The SVG emitter now raises instead (`RuntimeError` in Python, `TreescapeError` in Julia). No golden changed.
- **XML-forbidden control characters** (U+0000–U+0008, U+000B, U+000C, U+000E–U+001F, U+FFFE, U+FFFF) in tip names and labels are replaced with U+FFFD instead of producing a malformed document.
- **Julia host parity:** `-0.0`/`0.0` (and `1`/`1.0`) are one category, as in Python; callable structs are accepted as colormaps; huge finite `alpha` clamps instead of overflowing.
- **Newick tokenizers agree on Unicode:** branch-length digits are ASCII only and whitespace is Unicode White_Space in both the Rust core and `treescape-reference` (the reference accepted `'١'` as a digit and treated U+001C–U+001F as whitespace).

### Fixed — found by the Phase 2 fuzz runner

- **Newick: a `]` outside a comment hung the parser until the process ran out of memory** — in both the Rust core and `treescape-reference`, so `TreePlot("a];")` could take down a Python session. The tokenizer's name scanner stopped at `]` without advancing and appended empty names forever. Found by the Phase 2 fuzz runner; now a parse error (`unmatched ']' outside a comment`) with regression tests on both sides.

### Added — Phase 3: docs site

- **Docs site on GitHub Pages** (MkDocs Material, `docs/` + `mkdocs.yml`), built and deployed by `.github/workflows/docs.yml`: examples in Python and Julia side by side, conventions, the EVIDENT trust case, a claims page generated from `evident.yaml`, and the Julia package page.
- **Tested examples:** `tests/oracle/test_docs_examples.py` runs every Python and Julia block on the examples page and requires the SVG to equal the gallery image shown under it, byte for byte (coverage of `treescape-julia-python-svg-parity`; no new claim).
- `THIRD_PARTY_NOTICES.md`: everything treescape bundles, links, reproduces or tests against, with licenses.
- README rewritten (why / quickstart / what to trust, with the known limits of the evidence / design).

### Changed — Phase 3

- `treescape` no longer depends on `pandas` or `numpy`; `polars` is the only data-frame dependency.
- Repository layout: plans moved to `devdocs/plans/`, `CONTRIBUTING.md` to `.github/`.

### Fixed — review round 2 (Phase 2 fixes + Phase 3)

- **Julia use-after-free after an explicit `finalize(tree)`.** The finalizer freed the handle but kept the pointer, so a later render read freed memory (and could draw another tree). It now nulls the pointer; later calls fail with "tree is a null pointer", and a second `finalize` is a no-op.
- **Oversized Newick could abort the process (Python and Julia).** Parsing costs up to ~160× the input size, and Rust aborts on allocation failure: 63 MiB of `(` under an 8 GiB address-space cap killed the host. The parser's buffers now grow fallibly (`input too large to parse in available memory`, a `ValueError` in Python), and the C ABI limit is 16 MiB instead of 64 MiB. The no-abort runner now covers the size limit, the worst-case input at the limit, and an oversized buffer length.
- **Python/Julia parity:** a non-string `scale_bar` label is formatted as Python's `str()` (`1e-05`, `True`) in Julia too; a NaN or infinite `scale_bar` length is rejected at the call in both hosts; `alpha` so large that `alpha * 255` overflows clamps to opaque in Python too (it raised `OverflowError`); Julia render errors carry exactly Python's message (no `svg format error:` prefix). Two new parity cases pin the label bytes.
- **Newick claim now tests what it states.** `treescape-newick-roundtrip` claims exact topology agreement with Biopython, but the runner compared only tip names and tip branch lengths, and only for the reference parser. It now compares every clade and the branch length above it, for both the reference and the Rust parser, and includes the medium fixture (`primates.nwk`).
- **Claims page:** claim text containing `<fixture>`-style placeholders or `|` is escaped (the live page dropped `<fixture>` as an HTML tag); a claim missing a field fails the build with its id.
- **Font license:** the bundled `LICENSE.DejaVu.txt` lacked the Arev Fonts section that the font's own license (name ID 13) requires; it is now the font's license verbatim. The `treescape_connector` wheel ships both license files, and the crates that embed the font declare `MIT AND Bitstream-Vera`.
- **Docs wording:** the site no longer calls every oracle independent, states which oracles cover which layout (and that they check the Python reference on small fixtures), notes that determinism is verified on Linux, and no longer publishes a local path.
- **CI:** the release tier (ggtree) can be run manually on `main` before tagging (`workflow_dispatch`), as the trust case requires; Pages write permissions and the deploy queue are scoped to the deploy job, so pull-request builds can no longer cancel a pending deploy.
- **Tests:** the docs-example runner fails if any Python/Julia block on the page is not executed or an example's image is not the one shown under it; the parity runner fails on a misspelled table in `cases.toml`.

### Known limitations (v0.5.0)

- Metadata-driven branch styling is O(nodes × depth) — about 0.3 s for an 8,000-tip ladder tree. The pinned left-to-right Neumaier summation rules out combining child sums; a faster algorithm that preserves it is v0.6 work.
- Rust aborts on allocation failure. The Newick parser now grows its large buffers fallibly, and the C ABI caps input at 16 MiB, but small per-node allocations are still infallible, so parsing under extreme memory pressure can in principle still abort.
- Python and Julia still differ on a few inputs, in whether they succeed or raise, never in the bytes of a successful render: NUL characters in names (Julia rejects them, Python writes U+FFFD); several NaN keys in a discrete palette (Julia treats all NaNs as one category, Python as distinct values); Newick over 16 MiB (Python only); `cmap=` on a column of numeric strings (Python only).

## [0.4.0] — 2026-04-28

The complete-the-styling-story release. v0.3 shipped metadata-driven coloring on rectangular layouts and circular `highlight_clade` via annular sectors. v0.4 lifts every remaining `NotImplementedError` on circular layouts so they reach feature parity with rectangular for everything v0.3+v0.4 covers, adds **width** to the metadata-driven styling vocabulary, and lifts v0.3's "internal branches only" restriction so terminal branches participate in styling. After v0.4, "I want to publish this figure" should not hit a `NotImplementedError` for any combination of layout + metadata-driven attribute the trio covers. Two EVIDENT claims added, one amended, three extended; 227 / 31 / 8 oracle suite green; cargo workspace 46 + 11 green.

### Fixes (review rounds 1 + 2 + 3, post-phase-3)

- **`width_branches_by` no longer emits invalid SVG on non-finite values (round 1, P1).** NaN, inf, and −inf in observed numeric values flowed through `_column_value_range` and `_normalize` and ended up as `stroke-width="nan"` attributes — silent garbage, not valid SVG. Fixed by validating observed values and the `(vmin, vmax, wmin, wmax)` args with `math.isfinite` at the top of `width_branches_by`; negative `wmin` / `wmax` are also rejected (negative stroke widths are nonsensical).
- **Stale branch styles no longer survive chained styling calls (round 1, P2).** `_branch_colors` and `_branch_widths` were dicts that only added/updated entries on each metadata-driven styling call, so a second call where a branch became default (paraphyletic-by-current-column, all-missing, or — for width — an all-missing column) silently retained the *first* call's color or width. Each method now fully redefines the metadata-driven styling on its dimension. Width and color are independent dimensions, so each method redefines only its own map.
- **All-missing subtrees default silently — no warning (round 1, P2).** After v0.4 Phase 3 lifted the internal-only restriction, terminals whose tip was absent from the joined frame would warn every time `.color_branches_by` ran — noise, not signal. The user simply hadn't provided data there; that's not "miscoloring." Convention tightened to **warn iff the branch is paraphyletic AND has at least one observed value**. All-missing subtrees default silently, matching the continuous-color path's no-data convention. `docs/conventions.md` and the `treescape-color-branches-by-monophyly` claim text updated.
- **Failed branch-styling calls are atomic (round 2, P2).** The round-1 fix cleared `_branch_colors` / `_branch_widths` at the top of each method — but that ran *before* validation (palette resolution, non-numeric/non-finite checks). A failing call destroyed prior styling. Round 2 refactors both methods to build into a local map and assign at the end; failed validation now leaves prior state intact. Two atomicity tests added to verify a `ValueError` raise leaves `to_svg()` byte-identical to the pre-call render.
- **Atomicity holds under `warnings.simplefilter("error", TreescapeStyleWarning)` (round 3, P2).** Round 2's atomic-assign emitted `TreescapeStyleWarning` *after* the assignment — meaning a user pinning warnings-as-errors would see the call raise *and* the prior styling already replaced. Round 3 reorders: warnings emit first, then the atomic assign; the simplefilter raise interrupts before mutation. Regression test uses `simplefilter("error")` and asserts pre-call SVG bytes equal post-fail SVG bytes.
- **Convention doc rewritten for v0.4 terminal-branch lift (round 3, P2).** Three sections in `docs/conventions.md` still described v0.3's "internal branches only" rule, contradicting the v0.4 contract elsewhere in the same file. The discrete-branch-coloring section, the circular monophyly cross-reference, and the continuous numeric branch-coloring section are now rewritten to the v0.4 contract; the v0.3-only behavior is marked as historical with a v0.3.0 → v0.4.0 byte-change note.

### Phase 1 — circular `.color_tips` / `.color_tips_by` / `.color_branches_by`

Lifts the v0.3 `NotImplementedError` for tip and branch coloring on `.layout("circular")`. Same metadata-driven semantics as rectangular; the only circular-specific convention is which scene primitive carries the branch color.

- **Tip color** is per-`Text` `fill`, identical to the rectangular convention. No new scene primitive.
- **Branch color: which scene primitive carries it.** Locked: the **radial parent→child `Line`** receives the color; the **arc spine** (which connects siblings, not parent-to-child) stays at the default stroke color. Polar analogue of v0.3 rectangular's "horizontal segment colored, vertical spine default."
- **Monophyly + warn** semantics unchanged from v0.3; `TreescapeStyleWarning` names the offending branch and column on paraphyletic clades.
- **Continuous (subtree-mean viridis)** unchanged from v0.3 rectangular; tip and branch coloring share `(vmin, vmax)` by construction so the scales stay coherent on the same column.
- **Three EVIDENT claims extended** (no new claim IDs — same precedent v0.3 Phase 3 set when extending `treescape-styling-determinism` to circular highlights):
  - `treescape-color-tips-by-discrete-roundtrip` now covers rectangular AND circular. Rust↔ref byte parity holds because `tip_colors` is keyed by name (portable).
  - `treescape-color-branches-by-monophyly` now covers rectangular AND circular under the same monophyly + warn semantics.
  - `treescape-color-by-continuous-determinism` now covers rectangular AND circular with the same byte-determinism property and the same viridis LUT endpoints.

### Phase 2 — circular `.scale_bar` + `.support_labels`

Closes the last two `NotImplementedError` gates on circular. Both annotations reuse the same scene primitives the rectangular path uses (`Line` + `Text`); only positioning differs.

- **`.scale_bar` on circular: bottom-right radial bar.** Right endpoint anchored at `canvas_width − padding`; bar extends leftward by `length · px_per_r`. `bar_y = canvas_height − padding − font_size · 1.2`. Ticks + label same as rectangular. Bottom-right corner is reliably empty space outside the tree's inscribed circle on the square canvas.
- **Calibration-ring alternative explicitly rejected.** A circle's circumference is angular, not branch-length — using a ring as "scale" would visually suggest the wrong metric.
- **`.support_labels` on circular: upright text** (`rotation_deg = 0`, `anchor = Middle`) at the projected internal-node position. Tip labels rotate; support labels do not — short numerics like `95` or `0.97` stay legible at any tree position. Same `min_value` filter API as rectangular. Crowding at the tree's inner regions is a label-collision problem, deferred to v0.5+.
- **New EVIDENT claim** `treescape-circular-annotation-determinism` (ci-tier, property-style): same tree + same `(scale_bar, support_labels)` config → byte-identical SVG on the circular path. Includes convention assertions: scale-bar `bar_x2 == canvas_width − padding`; support-label `rotation_deg == 0` and `anchor == Middle`. One claim covers both annotations because they share the determinism property and the test fixture set.

### Phase 3 — `.width_branches_by` + terminal-branch coloring

v0.3 styling shipped color along the metadata-driven pipeline; v0.4 Phase 3 adds **width** to the same vocabulary, plus lifts v0.3's "internal branches only" rule so terminals participate.

- **`.width_branches_by(column, wmin=1.0, wmax=4.0, vmin=None, vmax=None)`** — numeric only. Linear interpolation onto `[wmin, wmax]` over `[vmin, vmax]`. Internal branch = subtree mean (matches `.color_branches_by` continuous); terminal branch = tip's own value (subtree of one). Subtrees with no observed values keep `SceneOptions.stroke_width` silently — same convention the continuous-color path uses for "no data is not paraphyletic miscoloring."
- **Default range** `(1.0, 4.0)` px chosen so the lower bound matches `SceneOptions.stroke_width`'s default — "minimum" width branches read visually identical to unstyled. User can override.
- **Default `(vmin, vmax)`** is the column's observed min/max so width and color stay coherent when applied to the same column. Out-of-range values clamped, not extrapolated. Degenerate range (`vmin == vmax` or all-equal values) deterministically maps every branch to width `(wmin + wmax) / 2`.
- **No discrete-by-width.** `.width_branches_by` raises `ValueError` on non-numeric columns. Width-by-discrete is rare and the `palette`/`cmap` symmetry doesn't translate cleanly to width; deferred unless a real fixture argues otherwise.
- **Terminal-branch coloring (lift on `.color_branches_by`).** v0.3 / v0.4 Phase 1 explicitly excluded terminal branches from `.color_branches_by`. Phase 3 lifts that exclusion: terminals participate in monophyly (trivially: one tip, one value, no warning) and in continuous mean (the tip's own value through `cmap`). When users call both `.color_tips_by("col")` and `.color_branches_by("col")` on the same column, the terminal branch and its tip carry the same color — what users expect from ggtree-style figures, what v0.3 quietly didn't deliver.
- **New EVIDENT claim** `treescape-branch-width-by-numeric-determinism` (ci-tier, property-style): byte-determinism for fixed inputs; subtree-mean rule on internal branches; tip-value rule on terminals; default-on-missing; clamp-on-outliers; raise-on-non-numeric.
- **Amended claim** `treescape-color-branches-by-monophyly`: claim text now covers internal AND terminal branches under the same monophyly + warn semantics.

### Gallery

`assets/gallery/` extended with three new files showing the v0.4 surface (per the plan's gallery success criterion):

- `11_circular_color_tips_by_clade.svg` — circular discrete tip color (Phase 1).
- `12_circular_scale_bar.svg` — circular bottom-right radial scale bar (Phase 2). The primates fixture has no internal-node names so a circular `.support_labels` example would be a no-op; we focus on the scale bar.
- `13_branch_width_by_support.svg` — branch-stroke width by numeric metadata (Phase 3). Subtree-mean on internals, tip-value on terminals, default range `(1.0, 4.0)` px.

Two existing gallery files regenerated under v0.4 Phase 3:

- `06_color_branches_by_clade.svg` — terminal branches now colored by their own monophyly-trivial value.
- `08_color_branches_by_support.svg` — same; terminals carry their tip's continuous value.

### EVIDENT manifest

- **18 claims pinned, all green.** v0.3 baseline was 16; v0.4 adds 2 new (`treescape-circular-annotation-determinism`, `treescape-branch-width-by-numeric-determinism`), amends 1 (`treescape-color-branches-by-monophyly` covers terminal branches), and extends 3 to circular layouts (`color-tips-by-discrete-roundtrip`, `color-branches-by-monophyly`, `color-by-continuous-determinism`).

### Backwards compatibility

- **v0.3 byte-determinism unchanged on existing test goldens.** No v0.3 fixture in `tests/fixtures/golden/` regenerated. The `test_styling_determinism.py` `STYLE_SPECS` use highlights + tip_colors only — the surfaces v0.4 changed (`color_branches_by` terminal lift, `width_branches_by` adding stroke widths) don't intersect those goldens.
- **Gallery 06 and 08 regenerated** because they exercise `.color_branches_by` and the terminal lift now applies. The gallery is documentation, not pinned bytes; users who pinned local bytes against those filenames need to re-render.
- **v0.3 styling claims still green over identical bytes** for fixtures that don't exercise terminal-branch coloring (which is everything in `STYLE_SPECS`).
- **No new runtime deps.** Polars is the only one on the styling path, already shipped in v0.3.

### Cuts deferred to v0.5+

- **PDF export.** Same scene graph, new emitter. Standalone enough to ship as v0.4.x or v0.5 Phase 1.
- **Nexus and PhyloXML parsers.** Each is ~1 phase; defer.
- **Node shape styling.** Would add a new `Marker(x, y, kind, size, fill, stroke)` scene type — net-new geometry. Considered for v0.4, deferred to keep Phase 3 scoped.
- **`.scale_bar` calibration-ring alternative on circular.** Rejected up-front in v0.4 Phase 2; not a deferred decision.
- **Discrete `.width_branches_by`.** Deferred unless a real fixture argues for it.
- **`treescape-cli` / `treeplot` console.** Surface design needs its own pass.
- **Label collision avoidance** (the GPU-pays-off case). Only matters at >10k tips; needs a real fixture to motivate.
- **Force-directed unrooted layout, kerning + non-Latin shaping, columnar-FFI variant for >50k tips × dense metadata.** Same v0.4-deferred list as v0.3.

## [0.3.0] — 2026-04-28

The metadata-driven-styling release. v0.2 shipped explicit dict-based `.color_tips({...})` and rectangular-only `.highlight_clade(...)`. v0.3 makes those automatic from joined metadata, adds continuous coloring, and lifts the circular-layout `NotImplementedError` for `.highlight_clade` via annular sectors. Five EVIDENT claims added or extended; 187 / 31 / 8 oracle suite green; cargo workspace 46 + 11 green.

### Phase 1 — `join_metadata` data-binding (polars-only)

- **`TreePlot.join_metadata(df, on=...)`** — chainable. Validates a `polars.DataFrame` against the tree's tip universe and stores per-tip rows for downstream coloring. Loud on every failure mode: extra rows whose `on=` value is not a tip raise `ValueError` with the offending count and first 5 names; duplicate `on=` values raise; chained-join column-name collisions raise (silent overwrite is the "which frame won?" failure mode that's hardest to debug). Empty frames are legal and produce all-`None` metadata for every tip with no warning.
- **Polars-only.** The plan considered dual-support and a `__dataframe__` interchange compromise; both rejected to keep maintenance flat. pandas users convert via `pl.from_pandas(df)`. One supported frame type, one error surface. Reconsider in a v0.x point release if user-reach demands.
- **Storage scope: Python-side, no FFI.** The joined frame is held on the `TreePlot` instance; `_metadata_for(tip_name)` returns a plain Python dict (column dtypes preserved as Python scalars). Phase 2 metadata-driven coloring resolves to `{tip_name: color}` dicts on the Python side and reuses the v0.2 styled-SVG path. The Rust `treescape-core` crate is unchanged. Trade-off disclosed: practical-N for metadata-driven plots is capped at Python dict overhead, not the SoA Rust core's actual capacity. Fine for v0.3's expected scale (≤10k tips × ≤10 columns); revisit in v0.4 with a columnar-FFI variant if the use case shows up.
- **New EVIDENT claim** `treescape-metadata-join-roundtrip` (ci-tier): every tip is queryable post-join; tips with no row return all-`None`; extra rows raise; duplicates raise; chained joins add columns and column-name collisions raise. v0.3 oracles the Python reference against itself (round-trip + explicit failure-mode tests) since there is no Rust port.
- **`treescape-reference/src/treescape_reference/metadata.py`** is the convention owner. Synthetic CSV fixtures at `tests/fixtures/metadata/small/{two_tip,balanced_4,unbalanced_5}.csv` — each chosen so at least one MRCA is monophyletic-by-`clade` and at least one is paraphyletic, giving Phase 2's branch-coloring claim both code paths from one fixture.
- **`polars>=1.0`** added to `treescape-reference` and `treescape` runtime deps.

### Phase 2 — metadata-driven branch & tip coloring

#### Discrete (categorical palette)

- **`TreePlot.color_tips_by(column, palette=...)`** maps a discrete metadata column through `palette` (defaults to **Tableau-10** in tree tip-order). User palettes must cover every observed non-`None` value; missing entries raise. More than 10 observed values with the default palette raise — no cycling, because cycling silently makes unrelated categories share color. Round-trip claim: `treescape-color-tips-by-discrete-roundtrip` (ci-tier) — produces the same per-tip colors as the equivalent explicit `.color_tips({...})` call.
- **`TreePlot.color_branches_by(column, palette=...)`** colors rectangular internal branches by **monophyly**: a branch is colored iff every descendant tip shares one non-missing value for `column`. Mixed or missing values leave the default branch color and emit `TreescapeStyleWarning` naming the branch and column. Diverges from ggtree's silent fallback; surfaces miscoloring instead of hiding. Standard `warnings.filterwarnings(...)` opts out — no custom toggle. Claim: `treescape-color-branches-by-monophyly` (ci-tier) — asserts both color *and* warning (or its absence on the monophyletic path) via `pytest.warns` / `warnings.catch_warnings`.
- The discrete EVIDENT claim was deliberately split into a tips claim and a branches-by-monophyly claim. Collapsing them was the "claim overstatement" anti-pattern v0.1 and v0.2 round-1 reviews caught — the tip path and the branch path exercise different code.
- Terminal branches are out of scope for v0.3's monophyly claim. They remain default-colored until a separate terminal-branch styling API lands.

#### Continuous (gradient)

- **Default colormap: viridis.** treescape ships its own pinned 11-keystop viridis LUT in `packages/treescape/src/treescape/plot.py::_VIRIDIS_LUT` with linear RGB interpolation between stops. Visually faithful to matplotlib's full 256-stop viridis; **byte-determinism is exact, full-256-stop fidelity is not**. Endpoints `#440154` at `t=0` and `#fde725` at `t=1`. A LUT change is a treescape-version-level break that regenerates golden bytes — track it explicitly in CHANGELOG.
- **API:** `color_tips_by(column, cmap=, vmin=, vmax=)` and `color_branches_by(column, cmap=, vmin=, vmax=)`. `cmap` accepts a string name (built-ins: `"viridis"`) or a callable `(t: float) -> "#rrggbb"`. Passing both `palette=` and `cmap=` raises `ValueError`. Auto-detection: if neither is given, all-numeric observed values (excluding `bool`) → continuous; otherwise → discrete.
- **Range:** `vmin` / `vmax` default to the column's observed min/max across the tree's tip universe — so tip and branch coloring on the same column share a coherent scale by construction. Values outside `[vmin, vmax]` are clamped, not extrapolated. **Degenerate range** (`vmin == vmax`, or all values equal) deterministically maps every value to `t = 0.5` (colormap midpoint) — no divide-by-zero.
- **Branch coloring (numeric):** each non-tip branch is colored by the **mean** of descendant tips' non-missing values, mapped through `cmap`. Subtrees with no observed values keep the default color **silently** — no warning, since "no data" is not a paraphyletic miscoloring (contrast with the discrete monophyly path, which warns on mixed/missing).
- **New EVIDENT claim** `treescape-color-by-continuous-determinism` (ci-tier, property-style): same column values + same `cmap` + same `(vmin, vmax)` → byte-identical SVG. 10 tests covering byte-determinism on tips and branches, default-cmap-is-viridis with LUT endpoints, vmin/vmax pin range and clamp outliers, degenerate range → midpoint, callable cmap honored, palette+cmap conflict raises, unknown cmap name raises, subtree-with-no-data is silent, auto-detect == explicit `cmap="viridis"`.

### Phase 3 — circular clade highlighting (annular sectors)

- **`TreePlot.layout("circular").highlight_clade(...)`** is now supported. The v0.2 `NotImplementedError` for circular highlights is lifted; v0.2 styled SVG bytes are unchanged.
- **New scene type: `AnnularSector(cx, cy, r_inner, r_outer, theta_min, theta_max, fill)`** in both `treescape-reference/scene.py` and `treescape-core/layout/scene.rs`. Coordinates in pixels (post-projection), matching `Rect`. Emitted before `Line`/`Arc`/`Text` so highlights render behind branches and labels — same z-order as the rectangular `Rect` highlight.
- **Geometry:** `r_inner = mrca_r * px_per_x` (MRCA's branch point); `r_outer = max_r * px_per_x + label_offset + max_label_px` (every highlight extends to the same outer radius — the polar analogue of v0.2's "rectangle to canvas right edge"). `theta_min`, `theta_max` are the min/max layout tip angles in `clade_tips(MRCA)` (internal-node angles do not bound the sector — only tip angles, matching the rectangular row-span convention).
- **MRCA == root → `ValueError`.** A clade whose MRCA is the root covers every tip — the highlight would cover the whole canvas (visually meaningless, blocks every branch and label). Loud-rejected at `to_svg`-time. Wrap-split paths are dead code under v0.3's `start_angle = π/2`, `sweep = 2π` convention; a fan layout (`sweep_total < 2π`) reopens the wrap question.
- **SVG emit:** `<path d="M ... L ... A ... L ... A ... Z" fill="...">`. Outer arc uses `sweep_flag = 0` (CCW visually under our SVG y-flip — same convention as the existing `Arc` spine); inner arc returns with `sweep_flag = 1`. `large_arc = 1` iff `theta_max − theta_min > π`. Float formatting matches the existing `Arc` renderer (`{:.4}` trim trailing zeros) — keeps Rust↔Python ref byte parity.
- **Connector:** new `render_circular_styled_svg(tree, opts, highlights)` PyO3 function. Maps `Result::Err` containing `"MRCA == root"` to `PyValueError`; other errors map to `PyRuntimeError`.
- **EVIDENT claim** `treescape-styling-determinism` is **extended**, not replaced. Byte-determinism property carries over unchanged. Additional property: an `AnnularSector`'s `[theta_min, theta_max]` equals the min/max layout tip angles in the clade. Rectangular↔circular shape equivalence under the polar transform is **not** claimed — each layout is byte-deterministic in its own conventions, no cross-shape parity. 8 new tests added (2× repeated render parity, 2× golden snapshot, 2× Rust↔Python ref byte parity, 1× MRCA == root raise at both ref and connector layers, 1× angular-bounds property). Two new goldens checked in: `tests/fixtures/golden/{balanced_4,unbalanced_5}_styled_circular.svg`.
- **Other circular styling features remain `NotImplementedError`.** v0.3 Phase 3 is highlights-only per the plan. The circular-path `NotImplementedError` is now per-feature: it names which of `.color_tips` / `.color_tips_by`, `.color_branches_by`, `.scale_bar`, `.support_labels` is in use, instead of catching all of them with one message. Each is a natural follow-up; not in v0.3 scope.

### Bonus rectangular grammar (not in the v0.3 plan, accepted)

- **`TreePlot.scale_bar(length, label=None)`** — draws a branch-length scale bar below rectangular trees. Length validated `> 0`. Raises `NotImplementedError` on `.layout("circular")` since circular has no horizontal axis to anchor a scale bar to.
- **`TreePlot.support_labels(min_value=None)`** — renders internal node names as support labels with optional numeric threshold filtering. Raises `NotImplementedError` on `.layout("circular")` for now (circular extension is a follow-up).
- The connector signature for `render_rectangular_styled_svg` grew to thread `branch_colors`, `scale_bar`, `support_labels`, `support_min`. v0.2 byte-determinism preserved on existing fixtures.

### EVIDENT manifest

- **16 claims pinned, all green.** v0.2 baseline was 11; v0.3 adds 4 new (`treescape-metadata-join-roundtrip`, `treescape-color-tips-by-discrete-roundtrip`, `treescape-color-branches-by-monophyly`, `treescape-color-by-continuous-determinism`) and extends `treescape-styling-determinism` to the circular path.

### Backwards compatibility

- **v0.2 `.color_tips({...})` and rectangular `.highlight_clade(...)` work unchanged.** v0.3 adds new entry points; it does not break or rename existing ones.
- **`treescape-svg-determinism` and `treescape-styling-determinism` byte-determinism** holds over identical bytes for fixtures that don't use metadata or circular highlights. Golden SVGs from v0.2 were not regenerated.
- **`polars>=1.0`** is a new runtime dep — see Phase 1.

### Cuts deferred to v0.4+

- **Circular `.color_tips` / `.color_tips_by` / `.color_branches_by` / `.support_labels`.** Each is a natural extension of the AnnularSector path geometry / Text fill / Line stroke pipelines but needs its own convention pass and oracle.
- **`.scale_bar` on circular layouts.** Probably belongs as a calibration ring at a fixed radius rather than a horizontal bar; design-decision deferred.
- **Branch-stroke width by metadata, node shape styling, terminal-branch coloring.**
- **Nexus and PhyloXML parsers, PDF export, `treescape-cli`, kerning + non-Latin shaping.** Same v0.4+ list as v0.2 deferred.
- **GPU label collision avoidance, force-directed unrooted layout.** v0.4+/v0.5+.
- **Columnar-FFI variant for metadata-driven coloring at >50k tips × dense metadata.** v0.3 ships Python-dict-side; revisit when a real-world fixture pushes against the budget.

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
