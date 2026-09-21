//! Trees from distance matrices: neighbor joining and UPGMA.
//!
//! Port of `treescape_reference.tree_build`, which owns the conventions
//! (`docs/conventions.md`, "Trees from distance matrices"). The active
//! list, the tie rule (first pair in `(p, q)` order), and the order of
//! every floating-point operation match the reference, so both build the
//! same tree, ties included.
//!
//! Storage is a flat `n × n` matrix: a new cluster takes over the slot of
//! the first cluster it joins, and the second slot is retired. Slot reuse
//! does not change any arithmetic; it keeps memory at `O(n²)`.

use crate::tree::{NodeId, Tree};

/// Tolerance of the symmetry check, relative to `max(1, |D[i][j]|)`.
pub const SYMMETRY_TOL: f64 = 1e-9;

/// Why a matrix, its labels, or a linkage matrix was rejected. `Display`
/// gives the same text as the reference's `DistanceMatrixError`.
#[derive(Debug, Clone, PartialEq)]
pub enum TreeBuildError {
    TooFewTaxa(usize),
    LabelCount { labels: usize, n: usize },
    NotSquare { len: usize },
    NotFinite { i: usize, j: usize, value: f64 },
    Negative { i: usize, j: usize, value: f64 },
    Diagonal { i: usize, value: f64 },
    Asymmetric { i: usize, j: usize, a: f64, b: f64 },
    EmptyLabel(usize),
    DuplicateLabel(String),
    LinkageRows { n: usize, rows: usize },
    LinkageCluster { row: usize },
    LinkageDistance { row: usize, value: f64 },
}

impl std::fmt::Display for TreeBuildError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::TooFewTaxa(n) => write!(f, "need at least 2 taxa, got {n}"),
            Self::LabelCount { labels, n } => write!(f, "{labels} labels for a {n} x {n} matrix"),
            Self::NotSquare { len } => {
                write!(f, "{len} matrix entries do not form a square matrix")
            }
            Self::NotFinite { i, j, value } => {
                write!(f, "D[{i}][{j}] is not finite ({})", py_float(*value))
            }
            Self::Negative { i, j, value } => {
                write!(f, "D[{i}][{j}] is negative ({})", py_float(*value))
            }
            Self::Diagonal { i, value } => {
                write!(
                    f,
                    "D[{i}][{i}] is {}; the diagonal must be 0",
                    py_float(*value)
                )
            }
            Self::Asymmetric { i, j, a, b } => write!(
                f,
                "D[{i}][{j}] = {} but D[{j}][{i}] = {}; the matrix is not symmetric",
                py_float(*a),
                py_float(*b)
            ),
            Self::EmptyLabel(i) => write!(f, "label {i} must be a non-empty string, got ''"),
            Self::DuplicateLabel(l) => write!(f, "duplicate label '{l}'"),
            Self::LinkageRows { n, rows } => {
                write!(
                    f,
                    "a linkage matrix for {n} labels has {} rows, got {rows}",
                    n.saturating_sub(1)
                )
            }
            Self::LinkageCluster { row } => write!(f, "linkage row {row} joins invalid clusters"),
            Self::LinkageDistance { row, value } => {
                write!(
                    f,
                    "linkage row {row} has invalid distance {}",
                    py_float(*value)
                )
            }
        }
    }
}

impl std::error::Error for TreeBuildError {}

/// Python's `str(float)` for the values that appear in error messages.
fn py_float(v: f64) -> String {
    if v.is_nan() {
        "nan".into()
    } else if v.is_infinite() {
        if v > 0.0 {
            "inf".into()
        } else {
            "-inf".into()
        }
    } else if v == v.trunc() && v.abs() < 1e16 {
        format!("{v:.1}")
    } else {
        format!("{v}")
    }
}

/// Check the input rules on a row-major `n × n` matrix.
pub fn validate(matrix: &[f64], labels: &[&str]) -> Result<usize, TreeBuildError> {
    let n = labels.len();
    let cells = matrix.len();
    let side = (cells as f64).sqrt() as usize;
    let side = if side * side == cells {
        side
    } else if (side + 1) * (side + 1) == cells {
        side + 1
    } else {
        return Err(TreeBuildError::NotSquare { len: cells });
    };
    if side < 2 {
        return Err(TreeBuildError::TooFewTaxa(side));
    }
    if n != side {
        return Err(TreeBuildError::LabelCount { labels: n, n: side });
    }
    let at = |i: usize, j: usize| matrix.get(i * n + j).copied().unwrap_or(f64::NAN);
    for i in 0..n {
        for j in 0..n {
            let v = at(i, j);
            if !v.is_finite() {
                return Err(TreeBuildError::NotFinite { i, j, value: v });
            }
            if v < 0.0 {
                return Err(TreeBuildError::Negative { i, j, value: v });
            }
        }
        let v = at(i, i);
        if v != 0.0 {
            return Err(TreeBuildError::Diagonal { i, value: v });
        }
    }
    for i in 0..n {
        for j in i + 1..n {
            let (a, b) = (at(i, j), at(j, i));
            if (a - b).abs() > SYMMETRY_TOL * a.abs().max(1.0) {
                return Err(TreeBuildError::Asymmetric { i, j, a, b });
            }
        }
    }
    validate_labels(labels)?;
    Ok(n)
}

fn validate_labels(labels: &[&str]) -> Result<(), TreeBuildError> {
    let mut seen = std::collections::HashSet::with_capacity(labels.len());
    for (i, label) in labels.iter().enumerate() {
        if label.is_empty() {
            return Err(TreeBuildError::EmptyLabel(i));
        }
        if !seen.insert(*label) {
            return Err(TreeBuildError::DuplicateLabel((*label).to_string()));
        }
    }
    Ok(())
}

/// Growing tree under construction: tips first (ids `0..n`), joins after.
struct Builder {
    tree: Tree,
}

impl Builder {
    fn new(labels: &[&str]) -> Self {
        let mut tree = Tree::new();
        for label in labels {
            let id = tree.add_node();
            if let Some(name) = tree.name.get_mut(id) {
                *name = (*label).to_string();
            }
        }
        Self { tree }
    }

    fn join(&mut self, children: &[(NodeId, f64)]) -> NodeId {
        let id = self.tree.add_node();
        for &(child, length) in children {
            if let (Some(p), Some(b), Some(c)) = (
                self.tree.parent.get_mut(child),
                self.tree.branch_len.get_mut(child),
                self.tree.children.get_mut(id),
            ) {
                *p = Some(id);
                *b = length;
                c.push(child);
            }
        }
        id
    }

    fn finish(mut self, root: NodeId) -> Tree {
        if let Some(b) = self.tree.branch_len.get_mut(root) {
            *b = 0.0;
        }
        self.tree.root = Some(root);
        self.tree.finalize();
        self.tree
    }
}

/// Symmetric working matrix from the upper triangle only.
fn upper(matrix: &[f64], n: usize) -> Vec<f64> {
    let mut d = vec![0.0; n * n];
    for i in 0..n {
        for j in i + 1..n {
            let v = matrix.get(i * n + j).copied().unwrap_or(0.0);
            if let Some(x) = d.get_mut(i * n + j) {
                *x = v;
            }
            if let Some(x) = d.get_mut(j * n + i) {
                *x = v;
            }
        }
    }
    d
}

fn pair(matrix: &[f64], labels: &[&str]) -> Tree {
    let mut b = Builder::new(labels);
    let half = matrix.get(1).copied().unwrap_or(0.0) / 2.0;
    let root = b.join(&[(0, half), (1, half)]);
    b.finish(root)
}

/// One active cluster: its node id, size, and height (UPGMA).
#[derive(Clone, Copy)]
struct Cluster {
    node: NodeId,
    size: usize,
    height: f64,
}

/// Distances between the active clusters, stored **in active-list order**
/// (row/column `i` is the `i`-th active cluster) in a row-major buffer
/// with stride `n`. Scans read contiguous rows; a join squeezes out the
/// two joined rows and columns in place and appends the new cluster last,
/// exactly as the active list does.
struct Active {
    d: Vec<f64>,
    n: usize,
    r: usize,
}

impl Active {
    fn new(matrix: &[f64], n: usize) -> Self {
        Self {
            d: upper(matrix, n),
            n,
            r: n,
        }
    }

    fn row(&self, i: usize) -> &[f64] {
        self.d.get(i * self.n..i * self.n + self.r).unwrap_or(&[])
    }

    fn get(&self, i: usize, j: usize) -> f64 {
        self.d.get(i * self.n + j).copied().unwrap_or(0.0)
    }

    /// Remove positions `p < q` and append a cluster whose distances to the
    /// remaining ones (in their new order) are `new_row`.
    fn join(&mut self, p: usize, q: usize, new_row: &[f64]) {
        let (n, r) = (self.n, self.r);
        let mut dest = 0;
        for i in 0..r {
            if i == p || i == q {
                continue;
            }
            // Row i without columns p and q, moved to row `dest`. Every
            // write goes to an index at or below its read, so forward copies
            // are safe in place.
            let (src, dst) = (i * n, dest * n);
            self.d.copy_within(src..src + p, dst);
            self.d.copy_within(src + p + 1..src + q, dst + p);
            self.d.copy_within(src + q + 1..src + r, dst + q - 1);
            dest += 1;
        }
        let last = r - 2;
        for (k, &v) in new_row.iter().enumerate() {
            if let Some(x) = self.d.get_mut(last * n + k) {
                *x = v;
            }
            if let Some(x) = self.d.get_mut(k * n + last) {
                *x = v;
            }
        }
        if let Some(x) = self.d.get_mut(last * n + last) {
            *x = 0.0;
        }
        self.r = r - 1;
    }
}

/// `total[k] = Σ_m d(k, m)`, summed left to right over the active list
/// (docs/conventions.md). Four rows are summed side by side, each with its
/// own accumulator, so every row keeps its exact addition order while the
/// four dependency chains overlap. The diagonal is added rather than
/// skipped: it is exactly `+0.0`, and adding `+0.0` to a sum that starts
/// at `+0.0` never changes it (round-to-nearest yields `+0`, not `-0`, for
/// `x + (-x)`), so the result is bit-identical to skipping it.
fn row_totals(dist: &Active, total: &mut [f64]) {
    let r = dist.r;
    let mut k = 0;
    while k + 4 <= r {
        let (r0, r1, r2, r3) = (
            dist.row(k),
            dist.row(k + 1),
            dist.row(k + 2),
            dist.row(k + 3),
        );
        let (mut s0, mut s1, mut s2, mut s3) = (0.0_f64, 0.0_f64, 0.0_f64, 0.0_f64);
        for (((a, b), c), d) in r0.iter().zip(r1).zip(r2).zip(r3) {
            s0 += a;
            s1 += b;
            s2 += c;
            s3 += d;
        }
        for (i, s) in [s0, s1, s2, s3].into_iter().enumerate() {
            if let Some(t) = total.get_mut(k + i) {
                *t = s;
            }
        }
        k += 4;
    }
    while k < r {
        let s = dist.row(k).iter().fold(0.0_f64, |acc, v| acc + v);
        if let Some(t) = total.get_mut(k) {
            *t = s;
        }
        k += 1;
    }
}

/// First pair `(p, q)`, `p < q`, minimizing `score(p, q)` (strict `<`).
fn argmin_pair(r: usize, mut score: impl FnMut(usize, usize) -> f64) -> (usize, usize, f64) {
    let (mut best, mut bp, mut bq) = (f64::INFINITY, 0, 1);
    let mut first = true;
    for p in 0..r {
        for q in p + 1..r {
            let value = score(p, q);
            if first || value < best {
                best = value;
                bp = p;
                bq = q;
                first = false;
            }
        }
    }
    (bp, bq, best)
}

/// Neighbor joining (Saitou & Nei 1987, Studier & Keppler criterion).
pub fn neighbor_joining(matrix: &[f64], labels: &[&str]) -> Result<Tree, TreeBuildError> {
    let n = validate(matrix, labels)?;
    if n == 2 {
        return Ok(pair(matrix, labels));
    }
    let mut dist = Active::new(matrix, n);
    let mut b = Builder::new(labels);
    let mut active: Vec<Cluster> = (0..n)
        .map(|i| Cluster {
            node: i,
            size: 1,
            height: 0.0,
        })
        .collect();
    let mut total = vec![0.0_f64; n];
    let mut new_row = Vec::with_capacity(n);

    while dist.r > 3 {
        let r = dist.r;
        row_totals(&dist, &mut total);
        let rm2 = (r - 2) as f64;
        let (p, q, _) = {
            let total = &total;
            let dist = &dist;
            argmin_pair(r, |p, q| {
                rm2 * dist.get(p, q)
                    - total.get(p).copied().unwrap_or(0.0)
                    - total.get(q).copied().unwrap_or(0.0)
            })
        };
        let (tp, tq) = (
            total.get(p).copied().unwrap_or(0.0),
            total.get(q).copied().unwrap_or(0.0),
        );
        let dpq = dist.get(p, q);
        let dp = dpq / 2.0 + (tp - tq) / (2 * (r - 2)) as f64;
        let dq = dpq - dp;
        let (Some(&cp), Some(&cq)) = (active.get(p), active.get(q)) else {
            break;
        };
        let u = b.join(&[(cp.node, dp), (cq.node, dq)]);
        new_row.clear();
        for k in 0..r {
            if k != p && k != q {
                new_row.push((dist.get(p, k) + dist.get(q, k) - dpq) / 2.0);
            }
        }
        dist.join(p, q, &new_row);
        active.remove(q);
        active.remove(p);
        active.push(Cluster {
            node: u,
            size: 0,
            height: 0.0,
        });
    }

    let [a, bb, c] = active[..] else {
        return Err(TreeBuildError::TooFewTaxa(active.len()));
    };
    let (dab, dac, dbc) = (dist.get(0, 1), dist.get(0, 2), dist.get(1, 2));
    let root = b.join(&[
        (a.node, (dab + dac - dbc) / 2.0),
        (bb.node, (dab + dbc - dac) / 2.0),
        (c.node, (dac + dbc - dab) / 2.0),
    ]);
    Ok(b.finish(root))
}

/// UPGMA: average linkage weighted by cluster size (Sokal & Michener 1958).
///
/// Distances stay in their original slots (a new cluster takes over the
/// slot of the first cluster it joins); `order` holds the slots in
/// active-list order. Each row caches its first minimum over the clusters
/// after it in list order. The global choice is the first row holding the
/// global minimum, which is exactly the first pair in `(p, q)` order. A
/// join only rescans rows whose cached minimum involved a joined cluster;
/// the others compare with the new cluster, which is last in list order,
/// so a strictly smaller value is needed to replace an earlier pair. The
/// values compared and the tie rule are the reference's; only the search
/// is faster.
pub fn upgma(matrix: &[f64], labels: &[&str]) -> Result<Tree, TreeBuildError> {
    let n = validate(matrix, labels)?;
    if n == 2 {
        return Ok(pair(matrix, labels));
    }
    let mut d = upper(matrix, n);
    let at = |d: &[f64], a: usize, b: usize| d.get(a * n + b).copied().unwrap_or(0.0);
    let mut b = Builder::new(labels);
    let mut cluster: Vec<Cluster> = (0..n)
        .map(|i| Cluster {
            node: i,
            size: 1,
            height: 0.0,
        })
        .collect();
    let mut order: Vec<usize> = (0..n).collect();
    // cache[slot] = (value, slot of the column) of the row's first minimum.
    let mut cache: Vec<Option<(f64, usize)>> = vec![None; n];
    let rescan = |d: &[f64], order: &[usize], pos: usize| -> Option<(f64, usize)> {
        let row = *order.get(pos)?;
        let mut out: Option<(f64, usize)> = None;
        for &col in order.iter().skip(pos + 1) {
            let v = at(d, row, col);
            if out.is_none_or(|(best, _)| v < best) {
                out = Some((v, col));
            }
        }
        out
    };
    for pos in 0..n {
        if let Some(&slot) = order.get(pos) {
            if let Some(c) = cache.get_mut(slot) {
                *c = rescan(&d, &order, pos);
            }
        }
    }

    while order.len() > 1 {
        let (mut ps, mut qs, mut best) = (0, 0, f64::INFINITY);
        let mut found = false;
        for &slot in &order {
            if let Some(Some((v, col))) = cache.get(slot) {
                if !found || *v < best {
                    (ps, qs, best, found) = (slot, *col, *v, true);
                }
            }
        }
        if !found {
            break;
        }
        let (Some(&cp), Some(&cq)) = (cluster.get(ps), cluster.get(qs)) else {
            break;
        };
        let h = best / 2.0;
        let u = b.join(&[(cp.node, h - cp.height), (cq.node, h - cq.height)]);
        let (sp, sq) = (cp.size as f64, cq.size as f64);
        let size = cp.size + cq.size;
        order.retain(|&s| s != ps && s != qs);
        for &k in &order {
            let v = (sp * at(&d, ps, k) + sq * at(&d, qs, k)) / size as f64;
            if let Some(x) = d.get_mut(ps * n + k) {
                *x = v;
            }
            if let Some(x) = d.get_mut(k * n + ps) {
                *x = v;
            }
        }
        // The new cluster reuses slot `ps` and goes last in list order.
        if let Some(c) = cluster.get_mut(ps) {
            *c = Cluster {
                node: u,
                size,
                height: h,
            };
        }
        order.push(ps);
        if let Some(c) = cache.get_mut(ps) {
            *c = None;
        }
        let last = order.len() - 1;
        for pos in 0..last {
            let Some(&slot) = order.get(pos) else {
                continue;
            };
            let current = cache.get(slot).copied().flatten();
            let updated = match current {
                Some((v, col)) if col != ps && col != qs => {
                    let v_new = at(&d, slot, ps);
                    if v_new < v {
                        Some((v_new, ps))
                    } else {
                        Some((v, col))
                    }
                }
                _ => rescan(&d, &order, pos),
            };
            if let Some(c) = cache.get_mut(slot) {
                *c = updated;
            }
        }
    }

    let root = order
        .first()
        .and_then(|&s| cluster.get(s))
        .map(|c| c.node)
        .unwrap_or(0);
    Ok(b.finish(root))
}

/// Tree from a SciPy linkage matrix (row-major, 4 columns per row); node
/// height = merge distance / 2.
pub fn from_linkage(linkage: &[f64], labels: &[&str]) -> Result<Tree, TreeBuildError> {
    let n = labels.len();
    let rows = linkage.len() / 4;
    if n < 2 || !linkage.len().is_multiple_of(4) || rows != n - 1 {
        return Err(TreeBuildError::LinkageRows { n, rows });
    }
    validate_labels(labels)?;
    let mut b = Builder::new(labels);
    let mut height = vec![0.0_f64; n];
    // Each cluster (tip or earlier row) is joined exactly once; reusing one
    // would drop or duplicate tips.
    let mut used = vec![false; 2 * n - 1];
    for row in 0..rows {
        let get = |c: usize| linkage.get(row * 4 + c).copied().unwrap_or(f64::NAN);
        let (a, bb, dist) = (get(0), get(1), get(2));
        let limit = (n + row) as f64;
        let valid = |x: f64| x.is_finite() && x == x.trunc() && x >= 0.0 && x < limit;
        let seen = |x: f64| used.get(x as usize).copied().unwrap_or(true);
        if !valid(a) || !valid(bb) || a == bb || seen(a) || seen(bb) {
            return Err(TreeBuildError::LinkageCluster { row });
        }
        if !dist.is_finite() || dist < 0.0 {
            return Err(TreeBuildError::LinkageDistance { row, value: dist });
        }
        let (a, bb) = (a as usize, bb as usize);
        for x in [a, bb] {
            if let Some(u) = used.get_mut(x) {
                *u = true;
            }
        }
        let h = dist / 2.0;
        let (ha, hb) = (
            height.get(a).copied().unwrap_or(0.0),
            height.get(bb).copied().unwrap_or(0.0),
        );
        b.join(&[(a, h - ha), (bb, h - hb)]);
        height.push(h);
    }
    let root = b.tree.len() - 1;
    Ok(b.finish(root))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::newick::write;

    const WIKI: [f64; 25] = [
        0., 5., 9., 9., 8., 5., 0., 10., 10., 9., 9., 10., 0., 8., 7., 9., 10., 8., 0., 3., 8., 9.,
        7., 3., 0.,
    ];

    #[test]
    fn nj_textbook_example() {
        let t = neighbor_joining(&WIKI, &["a", "b", "c", "d", "e"]).unwrap();
        assert_eq!(write(&t), "(d:2.0,e:1.0,(c:4.0,(a:2.0,b:3.0):3.0):2.0);");
    }

    #[test]
    fn upgma_is_ultrametric() {
        let t = upgma(&WIKI, &["a", "b", "c", "d", "e"]).unwrap();
        let root = t.root.unwrap();
        let mut depth = vec![0.0; t.len()];
        for id in t.preorder() {
            for &c in &t.children[id] {
                depth[c] = depth[id] + t.branch_len[c];
            }
        }
        let tips: Vec<f64> = (0..t.len())
            .filter(|&i| t.is_tip[i])
            .map(|i| depth[i])
            .collect();
        assert!(tips.iter().all(|d| (d - tips[0]).abs() < 1e-12), "{tips:?}");
        assert_eq!(t.branch_len[root], 0.0);
    }

    #[test]
    fn ties_take_the_first_pair() {
        // Four equidistant taxa: every pair ties; the first pair (a, b) joins first.
        let d = [
            0., 1., 1., 1., 1., 0., 1., 1., 1., 1., 0., 1., 1., 1., 1., 0.,
        ];
        let t = upgma(&d, &["a", "b", "c", "d"]).unwrap();
        assert_eq!(write(&t), "((a:0.5,b:0.5):0.0,(c:0.5,d:0.5):0.0);");
    }

    #[test]
    fn linkage_rejects_reused_clusters_and_bad_labels() {
        // Row 1 joins tip 0 again: that would orphan tip b.
        let e = from_linkage(&[0., 1., 2., 2., 0., 2., 2., 2.], &["a", "b", "c"]).unwrap_err();
        assert_eq!(e.to_string(), "linkage row 1 joins invalid clusters");
        let e = from_linkage(&[0., 1., 2., 2., 3., 3., 2., 2.], &["a", "b", "c"]).unwrap_err();
        assert_eq!(e.to_string(), "linkage row 1 joins invalid clusters");
        let e = from_linkage(&[0., 1., 2., 2., 2., 3., 2., 2.], &["a", "a", "c"]).unwrap_err();
        assert_eq!(e.to_string(), "duplicate label 'a'");
        assert!(from_linkage(&[0., 1., 2., 2., 2., 3., 2., 3.], &["a", "b", "c"]).is_ok());
    }

    #[test]
    fn rejects_bad_input_with_the_cell() {
        let e = neighbor_joining(&[0., 1., 2., 0.], &["a", "b"]).unwrap_err();
        assert_eq!(
            e.to_string(),
            "D[0][1] = 1.0 but D[1][0] = 2.0; the matrix is not symmetric"
        );
        let e = upgma(&[0., -1., -1., 0.], &["a", "b"]).unwrap_err();
        assert_eq!(e.to_string(), "D[0][1] is negative (-1.0)");
        let e = upgma(&[0., 1., 1., 0.], &["a", "a"]).unwrap_err();
        assert_eq!(e.to_string(), "duplicate label 'a'");
        assert!(upgma(&[0., 1., 1.], &["a", "b"]).is_err());
    }
}
