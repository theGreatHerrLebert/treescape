# Performance

Tree building from a distance matrix, measured by `scripts/bench_tree_build.py` (claim `treescape-tree-build-performance`). Every contender's tree is checked against treescape's before its time counts.

**Method.** median of 5 wall-clock runs after one warm-up (Biopython: 1 run); single thread; FFI hand-off included, matrix generation excluded; each contender's tree checked against treescape's first.

**Machine.** x86_64, 16 CPUs, Linux-5.15.0-191-generic-x86_64-with-glibc2.35, Python 3.12.13.

**Versions.** treescape 0.5.0, scikit-bio 0.7.3, SciPy 1.18.1, Biopython 1.88, NumPy 2.4.4.

## Neighbor joining

| n | treescape | scikit-bio | treescape / scikit-bio | Biopython | Biopython / treescape |
|---|---|---|---|---|---|
| 500 | 0.042 s | 0.021 s | 2.0× | 40.493 s | 955.9× |
| 1000 | 0.309 s | 0.114 s | 2.7× | 332.534 s | 1077.6× |
| 2000 | 3.183 s | 0.866 s | 3.7× | *not run (pure Python, too slow at this size)* | — |

## UPGMA

| n | treescape | SciPy (average linkage) | treescape / SciPy |
|---|---|---|---|
| 500 | 0.005 s | 0.001 s | 3.1× |
| 1000 | 0.020 s | 0.005 s | 3.7× |
| 2000 | 0.065 s | 0.027 s | 2.4× |

## Reading these numbers

- treescape's neighbor joining is the exact O(n³) algorithm with the summation order and tie rule pinned in `docs/conventions.md`, so that the Rust core and the Python reference build bit-identical trees. scikit-bio's optimized implementation is faster; treescape is much faster than Biopython's pure-Python implementation. Measured growth: time ∝ n^3.12.
- treescape's UPGMA uses cached row minima (typically O(n²)) with the same pinned tie rule; SciPy's nearest-neighbour chain is faster.
- Not measured: RapidNJ, FastME (specialist tools with heuristic speed-ups; not installed in this environment).
- Wall-clock numbers depend on the machine; the ratios are what the claim bounds.
