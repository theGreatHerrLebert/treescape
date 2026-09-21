# v0.6 plan

**Status: approved 2026-09-21** (user greenlight after v0.5.0; decisions 1 and 3 at their recommended defaults; decision 2: no MATLAB available; decision 4: course data moved to v0.7). Same cadence as v0.1–v0.5: tight scope, EVIDENT claims pinned **before** the code, Python reference first then Rust port, external review at the end of each phase.

## Theme

**Trees from distance matrices, on hardened evidence.**

The motivating use case is the Bioinformatics Practical (SS26). Students port MATLAB Bioinformatics Toolbox workflows to Julia, and plotting trees has been the sticking point for a long time. The MATLAB side builds trees in one line and plots them in another:

```matlab
distances = seqpdist(seqs, 'Method', 'Jukes-Cantor');
tree = seqlinkage(distances, 'UPGMA', seqs);      % humans, olfactory-receptor demos
NJtree = seqneighjoin(distances, 'equivar', seqs); % SARS demo
plot(tree, 'orient', 'bottom');
```

Julia has nothing equivalent that also gives deterministic, publication-ready output (see the v0.5 Julia landscape survey). v0.6 delivers `TreePlot(D, labels; method = :nj)` and the Python equivalent, held to independent oracles and tested on the course's real data.

Before any new capability lands, the new tree builders need oracle plumbing that the v0.5 claims audit (`devdocs/HANDOFF.md` step 3) found missing: external layout agreement rests on 4 tiny fixtures (2–5 tips), and every external oracle checks `treescape-reference`, never the Rust code. Phases 1–2 close that gap. Phase 3 builds on it.

## Proposed trio (in implementation order)

### Phase 1: EVIDENT schema migration and claim viewer on Pages

A structural change only: **no claim changes meaning, gains or loses coverage, or changes its command.** Doing it first means Phases 2–3 write claims in the final schema once, instead of twice.

- Bump the `evident/` submodule `bf990d2` → current upstream `main`.
- Migrate `evident.yaml` according to upstream `workflow/SCHEMA.md` → "Migration from v0":
  - add top-level `project: treescape` and a `vocabulary:` block (`subsystem`: parser, layout, tree-building, style, render, metadata, ffi, docs);
  - lift every `evidence.tolerance` prose string into structured `tolerances:` entries (`metric`/`op`/`value` where the prose states a number, `prose:` always);
  - add `subsystem`, `inputs` (corpus, n, class, fixture_path), `pinned_versions` (oracle versions currently written in prose);
  - process-rule claims become `kind: policy`.
- CI: validation moves from `evident/workflow/validate_manifest.py` to upstream `typed-trust`. Any rejected claim fails the build.
- Docs: `docs.yml` builds `typed-trust` and writes `typed-trust --format site evident.yaml > site/trust/index.html` after `mkdocs build`. The nav links it, and so does the generated `docs/claims.md`.
- **Acceptance:** `typed-trust` accepts all 21 claims. The `claim`, `command` and `artifact` text is unchanged, so the diff shows only structural moves. The claim viewer is live on Pages.
- **As implemented (2026-09-21), differences from the bullets above:**
  - The subsystem vocabulary is `parser, layout, text-metrics, render, style, metadata, julia-binding, ffi`. `tree-building` is added in Phase 3, when the first such claim exists.
  - Inputs name a corpus in `tests/fixtures/corpora.toml` and pin its `corpus_sha`, instead of a per-claim `fixture_path`.
  - CI runs **both** upstream gates, `validate_manifest.py --strict-release-pins` and `typed-trust`.
  - The viewer is rendered by the MkDocs hook into `docs/trust/`, so the strict build checks its link.
  - Oracle versions are pinned in `tests/requirements-oracles.txt` (CI and the release image), with Bioconductor at 3.22, and `tests/oracle/test_manifest.py` checks pins and hashes.
  - The review found four existing claim texts that the new structured fields contradict. They are listed in the CHANGELOG under "Noted, not changed" and wait for approval. Phase 2 resolves most of them.

### Phase 2: external layout agreement on real and random trees, against the Rust code

- **Pinned random corpus.** `scripts/gen_random_trees.py` (seeded, pure Python) writes `tests/fixtures/trees/random/*.nwk`: about 50 trees with 3–200 tips, covering Yule and uniform topologies, polytomies, zero-length branches, and ladders. The files are checked in and hashed (`corpus_sha`). They are pinned files rather than on-the-fly Hypothesis trees, so every oracle, including ggtree in the release image, sees the same input and a failure can be reproduced from a file name.
- **Oracles compare Rust directly.** `test_layout_vs_{ete3,biopython,ggtree}.py` and `test_circular_layout_vs_{ete3,ggtree}.py` compare **both** `treescape-reference` and the Rust connector against the external tool.
- **Coverage.** small/ + medium/ (adds `primates.nwk`) + the admissible edge/ fixtures + random/. `treescape-layout-rust-vs-reference` extends to the same set.
- **Disagreement discipline.** Each new convention difference that random trees surface is documented in `docs/conventions.md` with the fixture that exposes it. **Tolerances do not change.** A fixture that cannot be compared is excluded by name with a reason.
- **Platform scope.** Add a `macos-latest` leg for the determinism and golden tests, so the "across platforms" wording in `treescape-svg-determinism` is actually tested.
- **EVIDENT:** existing claim IDs keep their names. Their `inputs` and claim text grow to the new corpus and state which implementation each oracle checks.

### Phase 3: trees from distance matrices (NJ, UPGMA)

**API**

```python
TreePlot.from_distances(D, labels, method="nj")    # or "upgma"; D: 2-D array-like
TreePlot.from_linkage(Z, labels)                   # scipy.cluster.hierarchy linkage matrix
```

```julia
TreePlot(D, labels; method = :nj)                  # D::AbstractMatrix{<:Real}
```

The builders live in `treescape-core` (a new `tree_build` module that produces the existing struct-of-arrays tree), and the reference implementation comes first in `treescape_reference.tree_build`. Output is an ordinary tree, so every existing feature (circular layout, metadata join, styling, scale bar) works on it unchanged. A Newick writer round-trip lets users export the tree.

**Conventions to pin in `docs/conventions.md` before any code.** The result depends on each of these, and the oracles are known to differ:

- **NJ variant.** Saitou–Nei neighbor joining with the Studier–Keppler Q-criterion. To be confirmed: this is what MATLAB's `'equivar'` computes. MATLAB's other options (`'firstorder'`, `'average'`) are out of scope.
- **UPGMA.** Average linkage on the input distances, with node heights at half the merge distance (ultrametric), matching SciPy `linkage(method="average")` and MATLAB `seqlinkage(..., 'UPGMA')`.
- **Tie-breaking.** When several pairs share the minimum Q or distance, pick the lowest `(i, j)` in the current input order. The humans fixture has 6 zero-distance pairs, so ties are guaranteed and each oracle's tie rule is recorded.
- **Negative NJ branch lengths.** Keep them, as ape does. Any clamping must be explicit and documented, never silent.
- **Rooting of NJ trees.** Leave the root where the last join puts it (a trifurcation), or midpoint-root. Pin one choice, and record what MATLAB `seqneighjoin` returns.
- **Input validation.** Square, symmetric (exactly, or within a documented tolerance), zero diagonal, finite, non-negative, n ≥ 2, unique labels. Errors name the offending cell.

**Real-world fixtures** (`tests/fixtures/distances/`, labels + matrix as TSV, provenance in `DISTANCES.md`), from the course use cases:

| ID | n | Method in the demo | Source |
|---|---|---|---|
| `primates_hvr2_18` | 18 | UPGMA | `humans_demo`: HVR-II of humans, Neanderthal, chimp, bonobo, gorilla, orangutan, gibbon |
| `olfactory_gpcr_8`, `_10` | 8, 10 | UPGMA | `olfactoryreceptors_demo`: GPCR families ± two olfactory receptors |
| `cov_11` | 11 | NJ | `sars_demo`: coronavirus proteins incl. human SARS |
| `sars_spike_14` | 14 | NJ | `sars_demo`: 13 SARS spike genes + palm civet |
| `humans_mtdna_208` | 208 | UPGMA + NJ | `humans_demo` `D.mat`: 206 humans + 2 Neanderthals, precomputed Jukes–Cantor, 6 zero pairs |

`humans_mtdna_208` is taken verbatim from `D.mat`. The other matrices must be computed once, because the sequences are unaligned (unequal lengths). They are computed with MATLAB `seqpdist` using the exact demo arguments, if MATLAB is available (decision 2); otherwise with a pinned Biopython pairwise-alignment + Jukes–Cantor script. Checked-in matrices are the input to every claim, so distance computation itself is outside the evidence chain.

**Oracles** (independent lineages):

| Oracle | Checks | Tier |
|---|---|---|
| scikit-bio `nj` | NJ topology + branch lengths | ci |
| Biopython `DistanceTreeConstructor` (`nj`, `upgma`) | NJ + UPGMA | ci |
| SciPy `linkage(method="average")` | UPGMA topology + merge heights | ci |
| ape `nj()` + phangorn `upgma()` (R) | NJ + UPGMA | release |
| ~~MATLAB `seqneighjoin` / `seqlinkage` output~~ | dropped: no MATLAB available (decision 2) | — |

The comparison is on topology (unrooted splits for NJ, rooted clades for UPGMA) and branch lengths within 1e-9. It runs on the course fixtures plus random distance matrices, both additive (from random trees in the Phase 2 corpus, where NJ must recover the tree exactly) and non-additive. Oracle disagreements, most likely from ties and rooting, are documented, never absorbed.

**EVIDENT (pinned before code):**
- `treescape-nj-vs-oracles` (ci + release legs)
- `treescape-upgma-vs-oracles` (ci + release legs)
- `treescape-tree-build-rust-vs-reference` (ci): exact topology, branch lengths within 1e-12
- `treescape-nj-recovers-additive-trees` (ci, property-style): on additive matrices from the random corpus, NJ returns the generating unrooted tree
- `treescape-tree-build-performance` (bench job, `kind: measurement`): see the speed benchmark below
- `treescape-julia-python-svg-parity` extends to `from_distances` cases (no new ID)

**Speed benchmark.** The course fixtures (8–208 taxa) finish in milliseconds and say nothing about speed. "Fast" is only claimed once it is measured:

- **Workload:** synthetic matrices at n = 500, 1k, 2k, 5k, 10k. Each is generated by a seeded script (additive from a random tree plus seeded noise) and checked in as a generator + seed, not as data. `humans_mtdna_208` is included as the real-world point.
- **Contenders:**

  | Contender | Method | Sizes | Role |
  |---|---|---|---|
  | treescape (Rust, via Python and Julia) | NJ, UPGMA | all | measured |
  | scikit-bio `nj` | NJ | all | NJ baseline (NumPy) |
  | Biopython `DistanceTreeConstructor` | NJ, UPGMA | up to 2k (pure Python, cut at a 10-minute timeout) | baseline |
  | SciPy `linkage(method="average")` | UPGMA | all | UPGMA baseline (C) |
  | RapidNJ, FastME | NJ | all | reported only, not claimed against |

  RapidNJ and FastME are specialist C tools with heuristic speed-ups, so they are the honest ceiling; the table shows where treescape stands relative to them.
- **Correctness is checked first:** every timed run's tree must equal the oracle tree (same splits and lengths within 1e-9), so speed is never bought with a wrong answer.
- **Method:** wall-clock median of 5 runs after one warm-up. Each run is one process with a single thread. Matrix construction and I/O are excluded, and the FFI crossing is included, because that is what users pay. Hardware, OS, compiler and every tool version are recorded in the report.
- **Claim `treescape-tree-build-performance`** (a `kind: measurement` claim, run in a dedicated `bench` job on a pinned runner rather than ordinary CI, since shared runners are noisy):
  - treescape NJ is faster than scikit-bio `nj` and Biopython at every n ≥ 500, with the measured ratios reported;
  - treescape UPGMA is within a stated factor of SciPy (the factor is fixed from the first measurement, then held as a regression guard);
  - wall-clock growth is consistent with O(n³) for NJ.

  The claim text says how fast, against what, and on which machine. No bare "fast" appears in the README or docs.
- **Algorithm scope:** exact O(n³) NJ with a cache-friendly flat matrix. Heuristic speed-ups (RapidNJ-style branch and bound, NNI refinement) are out of scope for v0.6; the benchmark shows whether they are worth doing later.
- **Docs:** the benchmark table and plot go on a "Performance" page, regenerated by the `bench` job.

**As implemented (2026-09-21), differences from the text above:**
- The claims are split by tier, because a claim has a single tier: NJ and UPGMA each have a ci claim (scikit-bio + Biopython; SciPy) and a release claim (ape; phangorn). That makes seven new claims, not five.
- Biopython's `upgma` turned out to be WPGMA, and scikit-bio's `upgma` wraps SciPy. UPGMA is therefore checked against SciPy (ci) and phangorn (release) only.
- The performance claim bounds ratios instead of claiming speed. Measured: NJ is 2.0–3.7× slower than scikit-bio, UPGMA 2.3–3.9× slower than SciPy, and NJ is about 1,000× faster than Biopython. treescape is **not** faster than the optimized tools. Faster NJ moves to v0.7 (user decision, 2026-09-21).
- Benchmark sizes are 500, 1000 and 2000 (not up to 10k), because Biopython and exact O(n³) NJ make larger sizes impractical per run. RapidNJ and FastME are not installed and not measured.
- The course fixtures, the MATLAB oracle and the "Coming from MATLAB" page wait on decisions 2 and 4. The tested examples use the standard NJ teaching matrix instead.

**Docs:** a "Coming from MATLAB" page with the three demo workflows side by side: MATLAB, then Python, then Julia. Each example runs in CI like the existing examples page, and the output SVGs join the gallery.

Claim count after v0.6: 21 + 5 = **26**.

## Explicitly NOT in v0.6

- **Distances from sequences** (`seqpdist` equivalents: Jukes–Cantor, Kimura, p-distance, pairwise alignment). This is its own capability with its own oracles. Students compute D with the Julia bio stack; treescape starts from D. First candidate for v0.7.
- **Vertical (dendrogram-style) orientation**, `orient = bottom` in MATLAB. Both UPGMA demos use it, but it touches layout, render and every golden. v0.7 candidate (decision 3).
- **Other tree builders**: BIONJ, MATLAB `'firstorder'`, WPGMA, single/complete linkage, maximum likelihood.
- Render fidelity (SVG geometry vs validated coordinates), semantic styling claim, merging the six self-oracle determinism claims, and `treescape-tip-count-invariant` on Rust: moved to v0.7 as the second half of the claims audit.
- Newick vs a second parser; metadata join vs polars; Phylo.jl as a fourth oracle.
- Fan-layout API, matplotlib `cmap=`, `TreePlot._repr_svg_`, sub-quadratic branch styling, PyPI wheels, JLL/General registry.

## Cadence (same as v0.1–v0.5)

1. Lock conventions in `docs/conventions.md` **before** code.
2. Pin EVIDENT claims **before** tests. Approving this plan is the user's approval of the manifest changes listed here; any deviation goes back to the user.
3. Python reference first (random-tree generator, `tree_build`).
4. Rust port held to the reference.
5. Wire through both connectors (PyO3, C ABI + Julia).
6. External review per phase (Codex if available, otherwise independent Claude review agents); close findings before the next phase.
7. Commit + push per phase.

## Decisions (to lock)

1. **Scope order:** Phases 1–2 (evidence plumbing) before Phase 3 (NJ/UPGMA). Recommended, since Phase 3's oracles and random matrices reuse Phase 2's corpus and runners.
2. **MATLAB as a frozen oracle:** ~~can MATLAB be run once to export frozen reference trees?~~ **Decided 2026-09-21: no MATLAB is available.** There is no MATLAB oracle and no MATLAB-equivalence claim. The NJ variant rests on the published algorithm and on scikit-bio, Biopython and ape. If the course fixtures are published (decision 4), their distance matrices are computed with the pinned Biopython pairwise-alignment + Jukes–Cantor script (the fallback in Phase 3).
3. **Vertical orientation:** stays out of v0.6 (recommended), or replaces the macOS leg in Phase 2 as the one extra item.
4. **Publishing course data:** **Decided 2026-09-21: moved to v0.7.** v0.6 ships without course-derived data. The course fixtures (including the 208-taxon human mtDNA matrix as a real-world tie case) and the "Coming from MATLAB" page are v0.7 work; the tested examples use the standard NJ teaching matrix.

## Success criteria

v0.6 ships when:

- All three phases have landed on main.
- `typed-trust` accepts `evident.yaml`, and the claim viewer is live on Pages.
- ete3, Biopython and ggtree (release) compare **Rust** layout coordinates on the extended corpus, with tolerances unchanged.
- `TreePlot.from_distances` / `TreePlot(D, labels; method=…)` reproduce the oracle trees on all course fixtures, and the "Coming from MATLAB" page is executed in CI.
- 26 claims are green, CI is green (Rust, ci-tier Linux + macOS, Julia 1.10/1.12, docs), the `bench` job has published its report and Performance page, and release tier passes on the v0.6.0 tag.
- External review of all three phases closed, CHANGELOG updated, tag `v0.6.0` pushed.
