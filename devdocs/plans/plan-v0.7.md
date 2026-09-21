# v0.7 plan

**Status: approved 2026-09-21** (all decisions at the recommendations; decision 4 had none, so the MATLAB page uses public GenBank data unless the user allows the course data later). Same cadence as v0.1–v0.6: tight scope, EVIDENT claims pinned **before** the code, Python reference first then Rust port, external review at the end of each phase.

## Theme

**Usable in the practical: sequences in, a plotted tree out, installed without a Rust toolchain.**

v0.6 made treescape build trees from distance matrices. For the SS26 Bioinformatics Practical (students port MATLAB workflows to Julia), two gaps remain between a student and a plotted tree:

1. **Installation.** Today both packages have to be built from a checkout with a Rust toolchain. That is not something a course can ask of every student, so it is the biggest barrier by far.
2. **The first step.** The MATLAB demos start from sequences (`seqpdist`), not from a distance matrix.

v0.7 closes both, in the order a student meets them, and adds the one drawing option the demos rely on: the vertical dendrogram.

## Proposed trio (in implementation order)

### Phase 1: installable packages (Python wheels, Julia artifacts)

- **Python.** `maturin-action` builds `treescape_connector` wheels for Linux (manylinux, x86-64 and aarch64), macOS (arm64 and x86-64) and Windows (x86-64). `treescape` and `treescape-reference` are pure-Python wheels. On a `v*` tag they are published to PyPI through trusted publishing (decision 1). The DejaVu license already ships in the connector wheel (v0.5).
- **Julia.** The same CI builds `libtreescape_jl_connector` for the same platforms and attaches the tarballs to the GitHub release. `Treescape.jl` gains an `Artifacts.toml` pointing at them. Library discovery becomes: `ENV["TREESCAPE_JL_LIB"]`, then the Preferences.jl path, then **the artifact for this platform**, then the development build. Students install with `Pkg.add(url = "https://github.com/theGreatHerrLebert/treescape", subdir = "packages/Treescape.jl")`. Registering in the General registry and building a JLL through Yggdrasil are not part of v0.7 (decision 2).
- **EVIDENT (claims pinned before the code):**
  - New `treescape-installed-packages-reproduce-gallery` (release tier). In a clean environment on each built platform, the **installed** packages (the wheel from PyPI's staging index or the release assets, and the Julia artifact) reproduce every gallery SVG and the docs examples byte for byte. This tests what users actually install, not the development build.
  - `treescape-svg-determinism` extends to **Windows**: the claim's platform assumption grows from Linux and macOS to Windows. If Windows produces different bytes, that is a finding to fix, not to paper over.

### Phase 2: distances from aligned sequences

**API**

```python
from treescape import distances
D, labels = distances.from_fasta("aligned.fasta", model="jc69")   # or a list of (name, sequence)
TreePlot.from_distances(D, labels, method="nj")
TreePlot.from_sequences("aligned.fasta", model="jc69", method="nj")  # both steps in one call
```

```julia
D, labels = distances("aligned.fasta"; model = :jc69)
p = TreePlot(D, labels; method = :nj)
```

**Conventions to pin in `docs/conventions.md` before any code:**
- **Input: aligned sequences only.** All sequences must have the same length; otherwise it is an error that names the first sequence of a different length and says to align first. Pairwise alignment is not in v0.7 (decision 3). The docs show how to align with MAFFT or MUSCLE, or with Biopython's `PairwiseAligner` for two sequences.
- **Alphabets:** DNA/RNA (`ACGT`/`ACGU`, case-insensitive; `U` = `T`) and protein (the 20 amino acids). The alphabet is detected from the characters present, or set explicitly with `alphabet=`.
- **Gaps and ambiguity codes: pairwise deletion.** A site is used for a pair only if both sequences have a definite character there. This matches ape's `dist.dna(pairwise.deletion = TRUE)` and scikit-bio. A pair with no usable sites is an error.
- **Models:**
  - DNA: `p` (proportion of differing sites), `jc69` (Jukes–Cantor 1969), `k2p` (Kimura 1980, transitions and transversions).
  - Protein: `p`, `jc69` (the 20-state Jukes–Cantor form) and `poisson` (`−ln(1 − p)`). *(Corrected while pinning the conventions: "poisson" is not the 20-state Jukes–Cantor.)*

  Formulas are pinned with their references.
- **Saturation:** when a correction's logarithm is undefined (for example p ≥ 3/4 under JC69), the result is an error that names the pair and the observed p, never NaN or ∞ in the matrix.
- **FASTA reading:** first word of the header line = label; sequence lines are concatenated, whitespace is ignored; labels must be unique.

**Oracles:**

| Oracle | Checks | Tier |
|---|---|---|
| scikit-bio `pdist` / `jc69` / `k2p` | DNA p, JC69, K2P with gaps and ambiguity codes | ci |
| R ape `dist.dna(model = "raw"/"JC69"/"K80", pairwise.deletion = TRUE)` | the same, independent lineage | release |
| hand-computed | small alignments with a known p, including all-gap columns and saturation | ci |

**Corpus:** alignments simulated from the pinned random trees under JC69 and K2P (seeded; `scripts/gen_alignments.py`), plus hand-written edge cases (gaps, `N`, lowercase, RNA, protein, saturation).

**EVIDENT:** `treescape-seq-distances-vs-oracles` (ci), `treescape-seq-distances-vs-ape` (release), and `treescape-seq-distances-rust-vs-reference` (ci, exact within 1e-12). Julia↔Python parity extends to sequence input.

### Phase 3: vertical dendrograms and the practical-facing docs

- **Orientation:** `TreePlot(...).orientation("down")` (Python) / `orientation!(p, :down)` (Julia): root at the top, tips at the bottom, labels below the tips. Values are `"right"` (the current default, root on the left), `"down"`, `"left"` and `"up"`; the name gives the direction the tree grows. Only the rectangular layout is affected. The default output does not change: **zero golden regeneration**.
  - **Claim:** `treescape-orientation-is-a-rotation` (ci). For every tree in `layout-v2` and every orientation, each node's drawn position equals the validated rectangular coordinate under the documented rotation or reflection, exactly. Goldens for each orientation join `treescape-svg-determinism`.
- **Docs:**
  - A tested `from_linkage` example with a gallery image (from the v0.6 backlog).
  - An "From sequences" example: aligned FASTA → distances → NJ → vertical dendrogram, in Python and Julia, executed in CI like the other examples.
  - If decision 4 allows it, the **"Coming from MATLAB" page**: the three SS26 demo workflows side by side (MATLAB → Python → Julia), on published course-derived fixtures. Otherwise the page uses public data, for example an alignment of GenBank reference sequences with the accessions listed.
- **Small items that help the same users:** `TreePlot._repr_svg_` for Jupyter, and fan layouts (`start_angle` / `sweep_total`) exposed in both APIs.

## Explicitly NOT in v0.7

- **Pairwise or multiple sequence alignment** (decision 3). Users align with MAFFT, MUSCLE or Clustal Omega first.
- **Faster neighbor joining** (incremental totals, RapidNJ-style bounds, nearest-neighbour-chain UPGMA). Deferred from v0.6; still deferred.
- **The rest of the v0.5 claims audit:** render fidelity (checking SVG geometry against validated coordinates), a semantic styling claim, merging the six "same bytes twice" determinism claims, and moving the tip-count invariant to Rust. These are the leading candidates for v0.8; Phase 3's rotation claim is a first, narrow piece of render fidelity.
- JLL / Yggdrasil and General-registry registration (decision 2); conda packages.
- More distance models (F81, F84, TN93, LogDet, gamma rates), more tree builders (BIONJ, minimum evolution, WPGMA).
- matplotlib colormaps as `cmap=`, sub-quadratic branch styling, Phylo.jl as an oracle.

## Cadence (same as v0.1–v0.6)

For each phase:

1. Lock conventions in `docs/conventions.md` **before** any code.
2. Pin EVIDENT claims in `evident.yaml` **before** the tests exist. Approving this plan approves the manifest changes listed here; deviations go back to the user.
3. Python reference first (the distance models, the rotation).
4. Rust port held to the reference.
5. Wire through both connectors.
6. External review at the end of each phase: Codex if available, otherwise independent review agents plus the code-review skill. Close the findings before the next phase.
7. Commit and push per phase; run the release tier and the benchmark before the `v0.7.0` tag.

## Decisions (locked 2026-09-21)

PyPI trusted publishing uses workflow `.github/workflows/release.yml` and the GitHub environment `pypi` (created 2026-09-21; requires the owner's approval for every publish). The PyPI-side pending publishers are the user's one-time setup. No TestPyPI rehearsal (user decision): the wheels are tested installed in CI and checked with `twine check` before the gated upload; a bad upload is yanked and superseded by a patch release.


1. **PyPI:** publish to PyPI through trusted publishing (recommended). This needs a one-time setup by you: a PyPI account, and a trusted publisher for the three projects pointing at this repository's workflow. The alternative is GitHub release assets only (`pip install <url>`), which needs no account but is clumsier for students.
2. **Julia distribution:** artifacts from GitHub releases plus `Pkg.add(url = …)` (recommended; available this semester). The alternative is a JLL through Yggdrasil plus General-registry registration, which takes review time outside our control. That fits v0.8, once ABI 2 has held for a release.
3. **Unaligned sequences:** aligned input only (recommended). Pairwise alignment would be a whole capability of its own: scoring matrices, gap penalties, its own oracles.
4. **Course data** (still open from v0.6): may the course-derived matrices, alignments, labels and GenBank accessions be published? If yes, the "Coming from MATLAB" page uses the real demos.
5. **Orientation naming:** `"right" | "down" | "left" | "up"`, the direction the tree grows (recommended). The alternative is naming the root's side, `"left" | "top" | …`, which is closer to MATLAB's `'orient'` but ambiguous about what "top" refers to.

## Success criteria

v0.7 ships when:

- `pip install treescape` and `Pkg.add(url = …)` work on Linux, macOS and Windows without a Rust toolchain, and the installed packages reproduce the gallery byte for byte on each platform (release-tier claim).
- `distances` / `from_sequences` agree with scikit-bio (ci) and ape (release), and Rust matches the reference exactly.
- Vertical dendrograms are exact rotations of the validated layout, and existing goldens are unchanged.
- The "From sequences" example (and the "Coming from MATLAB" page if decision 4 allows it) runs in CI in both languages.
- All claims are green; external review of the three phases is closed; the CHANGELOG is updated; the release tier and the benchmark ran before the tag.
