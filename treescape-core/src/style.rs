//! Metadata-driven styling resolution (v0.5 Phase 1).
//!
//! Rust port of `treescape_reference.style`, which was extracted from the
//! v0.4 `plot.py`. Held to the reference with exact equality (claim
//! `treescape-style-resolution-rust-vs-reference`). Host-side concerns —
//! dataframes, dtype detection, color-string parsing, callable cmaps,
//! warning emission — are deliberately not here; see
//! docs/conventions.md, "Styling resolution in Rust (v0.5 Phase 1)".
//!
//! Columns are slices aligned to [`crate::ladderize::tip_order`]
//! (preorder tips): `Option<f64>` for numeric, `Option<u32>` codes for
//! discrete.

use std::fmt;

use crate::tree::{NodeId, Tree};

pub type Rgba = (u8, u8, u8, u8);

pub const TABLEAU_10: [&str; 10] = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#edc948", "#b07aa1", "#ff9da7",
    "#9c755f", "#bab0ac",
];

/// treescape's pinned viridis approximation: 11 keystops, linearly
/// interpolated. Not byte-identical to matplotlib's 256-stop viridis.
pub const VIRIDIS_LUT: [(u8, u8, u8); 11] = [
    (68, 1, 84),
    (72, 36, 117),
    (64, 65, 132),
    (52, 91, 140),
    (42, 116, 142),
    (34, 139, 141),
    (30, 161, 133),
    (68, 185, 116),
    (135, 206, 69),
    (211, 226, 45),
    (253, 231, 37),
];

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum StyleError {
    /// `t` was NaN. Message matches Python's `int(nan)` in v0.4.
    NanColor,
    /// More distinct values than the default palette covers.
    PaletteExhausted,
    /// Column length differs from the tree's tip count.
    ColumnLength { values: usize, tips: usize },
}

impl fmt::Display for StyleError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            StyleError::NanColor => write!(f, "cannot convert float NaN to integer"),
            StyleError::PaletteExhausted => {
                write!(f, "default categorical palette supports at most 10 values")
            }
            StyleError::ColumnLength { values, tips } => write!(
                f,
                "column has {values} value(s) but the tree has {tips} tip(s)"
            ),
        }
    }
}

impl std::error::Error for StyleError {}

/// Map `t in [0, 1]` through the pinned LUT. Channels round half to
/// even, as Python's `round()` did in v0.4.
pub fn viridis(t: f64) -> Result<Rgba, StyleError> {
    if t <= 0.0 {
        let (r, g, b) = VIRIDIS_LUT[0];
        return Ok((r, g, b, 255));
    }
    if t >= 1.0 {
        let (r, g, b) = VIRIDIS_LUT[VIRIDIS_LUT.len() - 1];
        return Ok((r, g, b, 255));
    }
    if t.is_nan() {
        return Err(StyleError::NanColor);
    }
    let n = (VIRIDIS_LUT.len() - 1) as f64;
    let pos = t * n;
    let lo = pos.trunc();
    let frac = pos - lo;
    let lo = lo as usize;
    let (r0, g0, b0) = VIRIDIS_LUT[lo];
    let (r1, g1, b1) = VIRIDIS_LUT[lo + 1];
    let channel = |c0: u8, c1: u8| -> u8 {
        let (c0, c1) = (f64::from(c0), f64::from(c1));
        (c0 + frac * (c1 - c0)).round_ties_even() as u8
    };
    Ok((channel(r0, r1), channel(g0, g1), channel(b0, b1), 255))
}

/// Tableau-10 in first-occurrence order; more than 10 values is an error.
pub fn default_palette(n_values: usize) -> Result<Vec<&'static str>, StyleError> {
    if n_values > TABLEAU_10.len() {
        return Err(StyleError::PaletteExhausted);
    }
    Ok(TABLEAU_10[..n_values].to_vec())
}

/// Float sum with CPython >= 3.12 builtin `sum()` semantics (Neumaier).
pub fn neumaier_sum(values: &[f64]) -> f64 {
    let mut total = 0.0_f64;
    let mut comp = 0.0_f64;
    for &x in values {
        let t = total + x;
        if total.abs() >= x.abs() {
            comp += (total - t) + x;
        } else {
            comp += (x - t) + total;
        }
        total = t;
    }
    if comp != 0.0 && comp.is_finite() {
        total += comp;
    }
    total
}

/// Python `min()`: keep the first value, replace on strict `<`.
fn py_min(values: &[f64]) -> Option<f64> {
    let (&first, rest) = values.split_first()?;
    Some(
        rest.iter()
            .fold(first, |acc, &v| if v < acc { v } else { acc }),
    )
}

/// Python `max()`: keep the first value, replace on strict `>`.
fn py_max(values: &[f64]) -> Option<f64> {
    let (&first, rest) = values.split_first()?;
    Some(
        rest.iter()
            .fold(first, |acc, &v| if v > acc { v } else { acc }),
    )
}

/// Observed `(lo, hi)` over non-missing values unless pinned; `(0, 1)`
/// when nothing is observed.
pub fn value_range(tip_values: &[Option<f64>], vmin: Option<f64>, vmax: Option<f64>) -> (f64, f64) {
    let numeric: Vec<f64> = tip_values.iter().flatten().copied().collect();
    let lo = vmin.unwrap_or_else(|| py_min(&numeric).unwrap_or(0.0));
    let hi = vmax.unwrap_or_else(|| py_max(&numeric).unwrap_or(1.0));
    (lo, hi)
}

/// Clamp to `[0, 1]`; degenerate ranges map to the midpoint 0.5.
pub fn normalize(value: f64, lo: f64, hi: f64) -> f64 {
    if hi <= lo {
        return 0.5;
    }
    // Same as Python's `if t < 0: 0 elif t > 1: 1 else t` — NaN and
    // -0.0 pass through unchanged.
    ((value - lo) / (hi - lo)).clamp(0.0, 1.0)
}

/// Per-node view of a tip-order-aligned column (`None` for internal nodes).
fn by_node<T: Copy>(tree: &Tree, tip_values: &[Option<T>]) -> Result<Vec<Option<T>>, StyleError> {
    let tips: Vec<NodeId> = tree
        .preorder()
        .into_iter()
        .filter(|&i| tree.is_tip[i])
        .collect();
    if tips.len() != tip_values.len() {
        return Err(StyleError::ColumnLength {
            values: tip_values.len(),
            tips: tips.len(),
        });
    }
    let mut out = vec![None; tree.len()];
    for (&node, &value) in tips.iter().zip(tip_values) {
        out[node] = value;
    }
    Ok(out)
}

/// Named descendant tips of `node`, left-to-right preorder.
pub fn descendant_tips(tree: &Tree, node: NodeId) -> Vec<NodeId> {
    let mut out = Vec::new();
    let mut stack = vec![node];
    while let Some(current) = stack.pop() {
        if tree.is_tip[current] {
            if !tree.name[current].is_empty() {
                out.push(current);
            }
        } else {
            stack.extend(tree.children[current].iter().rev());
        }
    }
    out
}

/// `(tip_name, t)` for every tip with a value, in tip order.
pub fn continuous_tip_t(
    tree: &Tree,
    tip_values: &[Option<f64>],
    lo: f64,
    hi: f64,
) -> Result<Vec<(String, f64)>, StyleError> {
    let values = by_node(tree, tip_values)?;
    Ok(tree
        .preorder()
        .into_iter()
        .filter(|&i| tree.is_tip[i])
        .filter_map(|i| values[i].map(|v| (tree.name[i].clone(), normalize(v, lo, hi))))
        .collect())
}

/// `(node, subtree mean)` for every non-root node with observed data, preorder.
fn subtree_means(
    tree: &Tree,
    tip_values: &[Option<f64>],
) -> Result<Vec<(NodeId, f64)>, StyleError> {
    let values = by_node(tree, tip_values)?;
    let mut out = Vec::new();
    for node in tree.preorder() {
        if Some(node) == tree.root {
            continue;
        }
        let numeric: Vec<f64> = descendant_tips(tree, node)
            .into_iter()
            .filter_map(|t| values[t])
            .collect();
        if numeric.is_empty() {
            continue; // no data → keep default, silent
        }
        out.push((node, neumaier_sum(&numeric) / numeric.len() as f64));
    }
    Ok(out)
}

/// `(node, t)` per branch from the subtree mean, preorder.
pub fn continuous_branch_t(
    tree: &Tree,
    tip_values: &[Option<f64>],
    lo: f64,
    hi: f64,
) -> Result<Vec<(NodeId, f64)>, StyleError> {
    Ok(subtree_means(tree, tip_values)?
        .into_iter()
        .map(|(n, m)| (n, normalize(m, lo, hi)))
        .collect())
}

/// `(node, width)` per branch from the subtree mean, preorder.
pub fn branch_widths(
    tree: &Tree,
    tip_values: &[Option<f64>],
    lo: f64,
    hi: f64,
    wmin: f64,
    wmax: f64,
) -> Result<Vec<(NodeId, f64)>, StyleError> {
    Ok(subtree_means(tree, tip_values)?
        .into_iter()
        .map(|(n, m)| (n, wmin + normalize(m, lo, hi) * (wmax - wmin)))
        .collect())
}

/// Result of the discrete monophyly rule.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct DiscreteBranches {
    /// `(node, code)` for branches whose named descendant tips all share
    /// one non-missing code, preorder.
    pub colored: Vec<(NodeId, u32)>,
    /// Branches with mixed or partial data, preorder. All-missing
    /// subtrees appear in neither list.
    pub non_monophyletic: Vec<NodeId>,
}

pub fn discrete_branch_codes(
    tree: &Tree,
    tip_codes: &[Option<u32>],
) -> Result<DiscreteBranches, StyleError> {
    let codes = by_node(tree, tip_codes)?;
    let mut out = DiscreteBranches::default();
    for node in tree.preorder() {
        if Some(node) == tree.root {
            continue;
        }
        let tips = descendant_tips(tree, node);
        let observed: Vec<u32> = tips.iter().filter_map(|&t| codes[t]).collect();
        let Some(&first) = observed.first() else {
            continue;
        };
        if observed.len() == tips.len() && observed.iter().all(|&c| c == first) {
            out.colored.push((node, first));
        } else {
            out.non_monophyletic.push(node);
        }
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::newick;

    #[test]
    fn viridis_endpoints_and_nan() {
        assert_eq!(viridis(0.0), Ok((68, 1, 84, 255)));
        assert_eq!(viridis(1.0), Ok((253, 231, 37, 255)));
        assert_eq!(viridis(-3.0), Ok((68, 1, 84, 255)));
        assert_eq!(viridis(f64::NAN), Err(StyleError::NanColor));
    }

    #[test]
    fn viridis_rounds_half_to_even() {
        // t = 0.05 → pos 0.5 between (68,1,84) and (72,36,117):
        // r = 70.0, g = 18.5 → 18 (even), b = 100.5 → 100 (even).
        assert_eq!(viridis(0.05), Ok((70, 18, 100, 255)));
    }

    #[test]
    fn neumaier_matches_python_312() {
        assert_eq!(neumaier_sum(&[1e16, 1.0, -1e16]), 1.0);
        assert_eq!(neumaier_sum(&[0.1; 10]), 1.0);
        assert_eq!(neumaier_sum(&[]), 0.0);
    }

    #[test]
    fn value_range_follows_python_min_max() {
        assert_eq!(
            value_range(&[None, Some(2.0), Some(1.0)], None, None),
            (1.0, 2.0)
        );
        assert_eq!(value_range(&[None], None, None), (0.0, 1.0));
        assert_eq!(value_range(&[Some(5.0)], Some(0.0), None), (0.0, 5.0));
        // NaN first: Python's min/max keep it (comparisons are false).
        let (lo, hi) = value_range(&[Some(f64::NAN), Some(1.0)], None, None);
        assert!(lo.is_nan() && hi.is_nan());
    }

    #[test]
    fn normalize_degenerate_and_clamp() {
        assert_eq!(normalize(3.0, 1.0, 1.0), 0.5);
        assert_eq!(normalize(-1.0, 0.0, 1.0), 0.0);
        assert_eq!(normalize(2.0, 0.0, 1.0), 1.0);
    }

    #[test]
    fn discrete_monophyly() {
        let tree = newick::parse("((a:1,b:1):1,(c:1,d:1):1);").unwrap();
        let res = discrete_branch_codes(&tree, &[Some(0), Some(0), Some(0), Some(1)]).unwrap();
        let colored_names: Vec<(String, u32)> = res
            .colored
            .iter()
            .map(|&(n, c)| (tree.name[n].clone(), c))
            .collect();
        // (a,b) clade + four terminals colored; (c,d) is mixed.
        assert_eq!(colored_names.len(), 5);
        assert_eq!(res.non_monophyletic.len(), 1);
    }

    #[test]
    fn column_length_mismatch_is_an_error() {
        let tree = newick::parse("(a:1,b:1);").unwrap();
        assert_eq!(
            continuous_branch_t(&tree, &[Some(1.0)], 0.0, 1.0),
            Err(StyleError::ColumnLength { values: 1, tips: 2 })
        );
    }
}
