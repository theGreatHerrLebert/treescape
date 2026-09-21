"""Tree-building benchmark (claim ``treescape-tree-build-performance``).

    python scripts/bench_tree_build.py [--sizes 500,1000,2000] [--out DIR]

For each size ``n`` a seeded matrix is built (path lengths of a seeded
Yule tree with ``n`` tips, each pair scaled by ``1 ± 0.1``). Each
contender runs one warm-up and then ``REPS`` timed runs; the median
wall-clock time is reported. Timing includes the hand-off from Python
(the ``flat`` list is prepared outside the timer, the FFI crossing is
inside), excludes matrix generation, and runs single-threaded
(``OMP_NUM_THREADS=1`` etc. are set before NumPy loads).

**Correctness first:** before a contender's time counts, its tree is
compared with treescape's (NJ unrooted splits, UPGMA rooted clade
heights, within 1e-9); a contender that builds a different tree is
reported as a mismatch, not timed.

Writes ``tree_build_performance.json`` (all numbers, the machine, every
version) and ``performance.md`` (the table for the docs site).
"""

from __future__ import annotations

import os

for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import argparse  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import platform  # noqa: E402
import random  # noqa: E402
import statistics  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tests" / "oracle"))

REPS = 5
SEED = 20260921
BIOPYTHON_MAX_N = 1000  # pure Python O(n^3); larger sizes take many minutes
TOL = 1e-9


def matrix(n: int):
    import numpy as np

    from gen_distance_matrices import patristic
    from gen_random_trees import _decorate, to_newick, yule

    rng = random.Random(f"{SEED}:{n}")
    root = yule(rng, n)
    _decorate(rng, root, 0.0)
    labels, m = patristic(to_newick(root))
    m = np.array(m)
    noise = np.triu(np.random.default_rng(SEED + n).uniform(-0.1, 0.1, (n, n)), 1)
    return labels, m * (1.0 + noise + noise.T)


def timed(fn, reps: int = REPS) -> tuple[float, object]:
    result = fn()  # warm-up; also the result checked for correctness
    times = []
    for _ in range(reps):
        start = time.perf_counter()
        fn()
        times.append(time.perf_counter() - start)
    return statistics.median(times), result


def run(sizes: list[int]) -> dict:
    import numpy as np
    import scipy
    import skbio
    from Bio import __version__ as bio_version
    from Bio.Phylo.TreeConstruction import DistanceMatrix as BioDM
    from Bio.Phylo.TreeConstruction import DistanceTreeConstructor
    from scipy.cluster.hierarchy import linkage
    from scipy.spatial.distance import squareform

    from _distances import from_clades, from_rust, heights, splits
    from treescape_connector.py_tree import Tree

    rows = []
    for n in sizes:
        labels, m = matrix(n)
        flat = m.ravel().tolist()
        entry: dict = {"n": n}

        t, ours_nj = timed(lambda: Tree.from_distances(flat, labels, "nj"))
        entry["treescape_nj"] = t
        ref_splits = splits(from_rust(ours_nj), labels[0])
        t, ours_up = timed(lambda: Tree.from_distances(flat, labels, "upgma"))
        entry["treescape_upgma"] = t
        ref_heights = heights(from_rust(ours_up))

        dm = skbio.DistanceMatrix(m, labels)
        t, tree = timed(lambda: skbio.tree.nj(dm, neg_as_zero=False))
        got = splits(from_clades(tree, lambda x: x.children, lambda x: x.length, lambda x: x.name), labels[0])
        entry["skbio_nj"] = t if _same_splits(got, ref_splits) else "mismatch"

        cond = squareform(m, checks=False)
        t, z = timed(lambda: linkage(cond, method="average"))
        entry["scipy_average"] = t if _same_heights(_scipy_heights(z, labels), ref_heights) else "mismatch"

        if n <= BIOPYTHON_MAX_N:
            lower = [[float(m[i][j]) for j in range(i + 1)] for i in range(n)]
            t, tree = timed(lambda: DistanceTreeConstructor().nj(BioDM(labels, lower)), reps=1)
            got = splits(from_clades(tree.root, lambda c: c.clades, lambda c: c.branch_length, lambda c: c.name), labels[0])
            entry["biopython_nj"] = t if _same_splits(got, ref_splits) else "mismatch"
        else:
            entry["biopython_nj"] = "not run (pure Python, too slow at this size)"
        rows.append(entry)
        print(json.dumps(entry), flush=True)

    return {
        "claim": "treescape-tree-build-performance",
        "method": f"median of {REPS} wall-clock runs after one warm-up (Biopython: 1 run); single thread; "
        "FFI hand-off included, matrix generation excluded; each contender's tree checked against treescape's first",
        "machine": {"platform": platform.platform(), "processor": platform.processor() or platform.machine(),
                    "python": platform.python_version(), "cpus": os.cpu_count()},
        "versions": {"treescape": _treescape_version(), "scikit-bio": skbio.__version__, "SciPy": scipy.__version__,
                     "Biopython": bio_version, "NumPy": np.__version__},
        "not_available": ["RapidNJ", "FastME"],
        "rows": rows,
    }


def _same_splits(a: dict, b: dict) -> bool:
    return set(a) == set(b) and all(abs(a[k] - b[k]) < TOL for k in a)


def _same_heights(a: dict, b: dict) -> bool:
    return set(a) == set(b) and all(abs(a[k] - b[k]) < TOL for k in a)


def _scipy_heights(z, labels) -> dict:
    n = len(labels)
    clade = {i: frozenset([labels[i]]) for i in range(n)}
    out = {clade[i]: 0.0 for i in range(n)}
    for row, (a, b, dist, _) in enumerate(z):
        clade[n + row] = clade[int(a)] | clade[int(b)]
        out[clade[n + row]] = float(dist) / 2
    return out


def _treescape_version() -> str:
    import tomllib

    return tomllib.loads((REPO / "Cargo.toml").read_text())["workspace"]["package"]["version"]


def exponent(rows: list[dict], key: str) -> float | None:
    """Least-squares slope of log(time) against log(n)."""
    pts = [(math.log(r["n"]), math.log(r[key])) for r in rows if isinstance(r.get(key), float)]
    if len(pts) < 2:
        return None
    mx = sum(x for x, _ in pts) / len(pts)
    my = sum(y for _, y in pts) / len(pts)
    return sum((x - mx) * (y - my) for x, y in pts) / sum((x - mx) ** 2 for x, _ in pts)


def markdown(report: dict) -> str:
    def cell(v):
        return f"{v:.3f} s" if isinstance(v, float) else f"*{v}*"

    def ratio(a, b):
        return f"{a / b:.1f}×" if isinstance(a, float) and isinstance(b, float) else "—"

    lines = [
        "# Performance",
        "",
        "Tree building from a distance matrix, measured by `scripts/bench_tree_build.py` "
        "(claim `treescape-tree-build-performance`). Every contender's tree is checked against "
        "treescape's before its time counts.",
        "",
        f"**Method.** {report['method']}.",
        "",
        f"**Machine.** {report['machine']['processor']}, {report['machine']['cpus']} CPUs, "
        f"{report['machine']['platform']}, Python {report['machine']['python']}.",
        "",
        "**Versions.** " + ", ".join(f"{k} {v}" for k, v in report["versions"].items()) + ".",
        "",
        "## Neighbor joining",
        "",
        "| n | treescape | scikit-bio | treescape / scikit-bio | Biopython | Biopython / treescape |",
        "|---|---|---|---|---|---|",
    ]
    for r in report["rows"]:
        lines.append(
            f"| {r['n']} | {cell(r['treescape_nj'])} | {cell(r['skbio_nj'])} | {ratio(r['treescape_nj'], r['skbio_nj'])} "
            f"| {cell(r['biopython_nj'])} | {ratio(r['biopython_nj'], r['treescape_nj'])} |"
        )
    lines += [
        "",
        "## UPGMA",
        "",
        "| n | treescape | SciPy (average linkage) | treescape / SciPy |",
        "|---|---|---|---|",
    ]
    for r in report["rows"]:
        lines.append(f"| {r['n']} | {cell(r['treescape_upgma'])} | {cell(r['scipy_average'])} | {ratio(r['treescape_upgma'], r['scipy_average'])} |")
    nj_exp = exponent(report["rows"], "treescape_nj")
    lines += [
        "",
        "## Reading these numbers",
        "",
        "- treescape's neighbor joining is the exact O(n³) algorithm with the summation order and tie rule "
        "pinned in `docs/conventions.md`, so that the Rust core and the Python reference build bit-identical "
        "trees. scikit-bio's optimized implementation is faster; treescape is much faster than Biopython's "
        "pure-Python implementation."
        + (f" Measured growth: time ∝ n^{nj_exp:.2f}." if nj_exp else ""),
        "- treescape's UPGMA uses cached row minima (typically O(n²)) with the same pinned tie rule; SciPy's "
        "nearest-neighbour chain is faster.",
        f"- Not measured: {', '.join(report['not_available'])} (specialist tools with heuristic speed-ups; "
        "not installed in this environment).",
        "- Wall-clock numbers depend on the machine; the ratios are what the claim bounds.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default="500,1000,2000")
    ap.add_argument("--out", default=str(REPO / "tests" / "oracle" / "reports"))
    args = ap.parse_args(argv)
    report = run([int(s) for s in args.sizes.split(",")])
    report["nj_exponent"] = exponent(report["rows"], "treescape_nj")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "tree_build_performance.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    (out / "performance.md").write_text(markdown(report))
    print(f"wrote {out / 'tree_build_performance.json'} and {out / 'performance.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
