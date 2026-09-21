//! Distances from aligned sequences: p, Jukes–Cantor, Kimura 2-parameter,
//! Poisson.
//!
//! Port of `treescape_reference.seq_distance`, which owns the conventions
//! (`docs/conventions.md`, "Distances from aligned sequences"). Same
//! alphabets, same pairwise deletion, same formulas in the same
//! floating-point order, saturation decided on the same integer counts,
//! and the same error messages.

use crate::tree_build::py_float;

const NUCLEOTIDE_DEFINITE: &[u8] = b"ACGT";
const NUCLEOTIDE_AMBIGUOUS: &[u8] = b"NRYSWKMBDHV";
const PROTEIN_DEFINITE: &[u8] = b"ACDEFGHIKLMNPQRSTVWY";
const PROTEIN_AMBIGUOUS: &[u8] = b"XBZJUO*";
const GAPS: &[u8] = b"-.";
/// FASTA whitespace: ASCII only (docs/conventions.md).
const WHITESPACE: &[char] = &[' ', '\t', '\r', '\u{0B}', '\u{0C}'];

/// Sequence alphabet.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Alphabet {
    Nucleotide,
    Protein,
}

impl Alphabet {
    fn name(self) -> &'static str {
        match self {
            Self::Nucleotide => "nucleotide",
            Self::Protein => "protein",
        }
    }
    fn models(self) -> &'static [&'static str] {
        match self {
            Self::Nucleotide => &["p", "jc69", "k2p"],
            Self::Protein => &["p", "jc69", "poisson"],
        }
    }
    fn definite(self) -> &'static [u8] {
        match self {
            Self::Nucleotide => NUCLEOTIDE_DEFINITE,
            Self::Protein => PROTEIN_DEFINITE,
        }
    }
}

/// Why sequences, labels or a model were rejected. The message is the
/// reference's `SequenceError` text.
#[derive(Debug, Clone, PartialEq)]
pub struct SequenceError(pub String);

impl std::fmt::Display for SequenceError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

impl std::error::Error for SequenceError {}

fn err<T>(msg: String) -> Result<T, SequenceError> {
    Err(SequenceError(msg))
}

/// Python `ascii()` of a string, as in the reference's messages: `repr`
/// with every character outside printable ASCII escaped as `\xhh`,
/// `\uhhhh` or `\Uhhhhhhhh`. (`ascii` rather than `repr` so that the rule
/// needs no Unicode tables and the two implementations agree exactly.)
pub(crate) fn repr(s: &str) -> String {
    let quote = if s.contains('\'') && !s.contains('"') {
        '"'
    } else {
        '\''
    };
    let mut out = String::with_capacity(s.len() + 2);
    out.push(quote);
    for c in s.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c == quote => {
                out.push('\\');
                out.push(c);
            }
            c if !printable(c) => {
                let v = c as u32;
                if v <= 0xFF {
                    out.push_str(&format!("\\x{v:02x}"));
                } else if v <= 0xFFFF {
                    out.push_str(&format!("\\u{v:04x}"));
                } else {
                    out.push_str(&format!("\\U{v:08x}"));
                }
            }
            c => out.push(c),
        }
    }
    out.push(quote);
    out
}

/// Printable ASCII (`ascii()` escapes everything else).
fn printable(c: char) -> bool {
    matches!(c, ' '..='~')
}

/// Number of FASTA records (header lines), counted without building them.
pub fn count_records(text: &str) -> usize {
    text.split('\n')
        .filter(|raw| raw.trim_start_matches(WHITESPACE).starts_with('>'))
        .count()
}

/// `true` if `source` is FASTA text: it starts with `>` after whitespace.
pub fn is_fasta_text(source: &str) -> bool {
    source
        .trim_start_matches(|c| WHITESPACE.contains(&c) || c == '\n')
        .starts_with('>')
}

/// `(label, sequence)` records from FASTA text: lines split on `\n`, a
/// trailing `\r` dropped, ASCII whitespace only.
pub fn read_fasta(text: &str) -> Result<Vec<(String, String)>, SequenceError> {
    let mut records: Vec<(String, String)> = Vec::new();
    for (number, raw) in text.split('\n').enumerate() {
        let line = raw
            .strip_suffix('\r')
            .unwrap_or(raw)
            .trim_matches(WHITESPACE);
        if line.is_empty() {
            continue;
        }
        if let Some(header) = line.strip_prefix('>') {
            let Some(label) = header.split(WHITESPACE).find(|w| !w.is_empty()) else {
                return err(format!("FASTA line {}: empty header", number + 1));
            };
            records.push((label.to_string(), String::new()));
        } else {
            let Some(last) = records.last_mut() else {
                return err(format!(
                    "FASTA line {}: sequence data before the first '>' header",
                    number + 1
                ));
            };
            last.1
                .extend(line.chars().filter(|c| !WHITESPACE.contains(c)));
        }
    }
    Ok(records)
}

/// `nucleotide` if every character of every uppercased sequence is a
/// nucleotide code, `U` or a gap, else `protein`.
pub fn detect_alphabet(seqs: &[Vec<u8>]) -> Alphabet {
    let nucleotide = |c: &u8| {
        *c == b'U'
            || NUCLEOTIDE_DEFINITE.contains(c)
            || NUCLEOTIDE_AMBIGUOUS.contains(c)
            || GAPS.contains(c)
    };
    if seqs.iter().all(|s| s.iter().all(nucleotide)) {
        Alphabet::Nucleotide
    } else {
        Alphabet::Protein
    }
}

/// Auto-detection chose nucleotide, but more than half of the non-gap
/// characters are nucleotide ambiguity codes: the hosts warn
/// (docs/conventions.md). Only meaningful when auto chose nucleotide.
pub fn auto_detection_is_doubtful(records: &[(String, String)]) -> bool {
    let (mut total, mut ambiguous) = (0usize, 0usize);
    for (_, s) in records {
        for c in s.bytes().map(|b| b.to_ascii_uppercase()) {
            if GAPS.contains(&c) {
                continue;
            }
            total += 1;
            ambiguous += usize::from(NUCLEOTIDE_AMBIGUOUS.contains(&c));
        }
    }
    total > 0 && 2 * ambiguous > total
}

/// Parse `"auto" | "nucleotide" | "protein"`.
pub fn parse_alphabet(name: &str) -> Result<Option<Alphabet>, SequenceError> {
    match name {
        "auto" => Ok(None),
        "nucleotide" => Ok(Some(Alphabet::Nucleotide)),
        "protein" => Ok(Some(Alphabet::Protein)),
        other => err(format!(
            "alphabet must be 'auto', 'nucleotide' or 'protein', got {}",
            repr(other)
        )),
    }
}

/// Check the input rules; return normalized sequences and the alphabet.
pub fn validate(
    records: &[(String, String)],
    alphabet: &str,
) -> Result<(Vec<Vec<u8>>, Alphabet), SequenceError> {
    if records.len() < 2 {
        return err(format!("need at least 2 sequences, got {}", records.len()));
    }
    let mut seen = std::collections::HashSet::new();
    for (i, (label, _)) in records.iter().enumerate() {
        if label.is_empty() {
            return err(format!("label {i} must be a non-empty string, got ''"));
        }
        if !seen.insert(label.as_str()) {
            return err(format!("duplicate label {}", repr(label)));
        }
    }
    for (label, seq) in records {
        if let Some((column, c)) = seq.chars().enumerate().find(|(_, c)| !c.is_ascii()) {
            return err(format!(
                "sequence {} has {} at column {}; sequences must be ASCII",
                repr(label),
                repr(&c.to_string()),
                column + 1
            ));
        }
    }
    let mut seqs: Vec<Vec<u8>> = records
        .iter()
        .map(|(_, s)| s.to_ascii_uppercase().into_bytes())
        .collect();
    let first_len = seqs.first().map(Vec::len).unwrap_or(0);
    let first_label = records.first().map(|r| r.0.as_str()).unwrap_or("");
    for ((label, _), seq) in records.iter().zip(&seqs) {
        if seq.len() != first_len {
            return err(format!(
                "sequence {} has length {}, but {} has {first_len}; the sequences must be aligned \
                 (use MAFFT, MUSCLE or Clustal Omega first)",
                repr(label),
                seq.len(),
                repr(first_label)
            ));
        }
    }
    let alphabet = parse_alphabet(alphabet)?.unwrap_or_else(|| detect_alphabet(&seqs));
    if alphabet == Alphabet::Nucleotide {
        for c in seqs.iter_mut().flat_map(|s| s.iter_mut()) {
            if *c == b'U' {
                *c = b'T';
            }
        }
    }
    let ambiguous = match alphabet {
        Alphabet::Nucleotide => NUCLEOTIDE_AMBIGUOUS,
        Alphabet::Protein => PROTEIN_AMBIGUOUS,
    };
    for ((label, _), seq) in records.iter().zip(&seqs) {
        for (column, &c) in seq.iter().enumerate() {
            if !(alphabet.definite().contains(&c) || ambiguous.contains(&c) || GAPS.contains(&c)) {
                return err(format!(
                    "sequence {} has {} at column {}, not a {} character",
                    repr(label),
                    repr(&char::from(c).to_string()),
                    column + 1,
                    alphabet.name()
                ));
            }
        }
    }
    Ok((seqs, alphabet))
}

fn is_transition(x: u8, y: u8) -> bool {
    let purine = |c: u8| c == b'A' || c == b'G';
    let pyrimidine = |c: u8| c == b'C' || c == b'T';
    (purine(x) && purine(y)) || (pyrimidine(x) && pyrimidine(y))
}

/// Distance between two normalized sequences of one alphabet.
pub fn pair_distance(
    a: &[u8],
    b: &[u8],
    alphabet: Alphabet,
    model: &str,
    names: (&str, &str),
) -> Result<f64, SequenceError> {
    let definite = alphabet.definite();
    let (mut usable, mut transitions, mut other) = (0usize, 0usize, 0usize);
    for (&x, &y) in a.iter().zip(b) {
        if !definite.contains(&x) || !definite.contains(&y) {
            continue;
        }
        usable += 1;
        if x == y {
            continue;
        }
        if is_transition(x, y) {
            transitions += 1;
        } else {
            other += 1;
        }
    }
    let pair = format!("{} and {}", repr(names.0), repr(names.1));
    if usable == 0 {
        return err(format!(
            "{pair} share no column where both have a definite character"
        ));
    }
    let diffs = transitions + other;
    if diffs == 0 && matches!(model, "p" | "jc69" | "k2p" | "poisson") {
        // Every correction is -c * ln(1) = -0.0 here; identical sequences
        // are at distance +0.0 (docs/conventions.md).
        return Ok(0.0);
    }
    let p = diffs as f64 / usable as f64;
    // Saturation is decided on exact integer counts (docs/conventions.md).
    match model {
        "p" => Ok(p),
        "jc69" => {
            let k_int: usize = if alphabet == Alphabet::Nucleotide {
                4
            } else {
                20
            };
            let k = k_int as f64;
            let b_ = (k - 1.0) / k;
            if k_int * diffs >= (k_int - 1) * usable {
                return err(format!(
                    "{pair}: p = {} is saturated for jc69 (needs p < {})",
                    py_float(p),
                    py_float(b_)
                ));
            }
            Ok(-b_ * (1.0 - p / b_).ln())
        }
        "k2p" => {
            let n1 = usable as i64 - 2 * transitions as i64 - other as i64;
            let n2 = usable as i64 - 2 * other as i64;
            if n1 <= 0 || n2 <= 0 {
                return err(format!(
                    "{pair}: P = {}, Q = {} are saturated for k2p",
                    py_float(transitions as f64 / usable as f64),
                    py_float(other as f64 / usable as f64)
                ));
            }
            Ok(-0.5 * (n1 as f64 / usable as f64).ln() - 0.25 * (n2 as f64 / usable as f64).ln())
        }
        "poisson" => {
            if diffs >= usable {
                return err(format!(
                    "{pair}: p = {} is saturated for poisson (needs p < 1)",
                    py_float(p)
                ));
            }
            Ok(-(1.0 - p).ln())
        }
        other => err(format!("unknown model {}", repr(other))),
    }
}

/// [`distance_matrix`], plus whether hosts should warn that auto-detection
/// chose nucleotide for what looks like protein (docs/conventions.md).
pub fn distance_matrix_checked(
    records: &[(String, String)],
    model: &str,
    alphabet: &str,
) -> Result<(Vec<f64>, Vec<String>, bool), SequenceError> {
    let (matrix, labels) = distance_matrix(records, model, alphabet)?;
    let doubtful = alphabet == "auto"
        && validate(records, "auto")
            .map(|(_, a)| a == Alphabet::Nucleotide)
            .unwrap_or(false)
        && auto_detection_is_doubtful(records);
    Ok((matrix, labels, doubtful))
}

/// Row-major `n × n` distance matrix (upper triangle computed, mirrored)
/// and the labels in input order.
pub fn distance_matrix(
    records: &[(String, String)],
    model: &str,
    alphabet: &str,
) -> Result<(Vec<f64>, Vec<String>), SequenceError> {
    let (seqs, alphabet) = validate(records, alphabet)?;
    let models = alphabet.models();
    if !models.contains(&model) {
        let listed = models
            .iter()
            .map(|m| repr(m))
            .collect::<Vec<_>>()
            .join(", ");
        return err(format!(
            "model {} is not available for {} sequences (choose from ({listed}))",
            repr(model),
            alphabet.name()
        ));
    }
    let n = seqs.len();
    let mut m = vec![0.0; n * n];
    for i in 0..n {
        for j in i + 1..n {
            let (Some(a), Some(b)) = (seqs.get(i), seqs.get(j)) else {
                continue;
            };
            let names = (
                records.get(i).map(|r| r.0.as_str()).unwrap_or(""),
                records.get(j).map(|r| r.0.as_str()).unwrap_or(""),
            );
            let d = pair_distance(a, b, alphabet, model, names)?;
            if let Some(x) = m.get_mut(i * n + j) {
                *x = d;
            }
            if let Some(x) = m.get_mut(j * n + i) {
                *x = d;
            }
        }
    }
    Ok((m, records.iter().map(|r| r.0.clone()).collect()))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn recs(pairs: &[(&str, &str)]) -> Vec<(String, String)> {
        pairs
            .iter()
            .map(|(a, b)| (a.to_string(), b.to_string()))
            .collect()
    }

    #[test]
    fn pairwise_deletion_and_models() {
        let r = recs(&[("x", "ACGTACGTAC"), ("y", "GCGTACGTAT")]);
        let (m, _) = distance_matrix(&r, "k2p", "auto").unwrap();
        assert!((m[1] - 0.255_412_811_882_995_36).abs() < 1e-15);
        let r = recs(&[("a", "ACGT-ACGTN"), ("b", "ACGA-TCGTA")]);
        let (m, _) = distance_matrix(&r, "p", "auto").unwrap();
        assert_eq!(m[1], 0.25);
    }

    #[test]
    fn identical_sequences_are_at_plus_zero() {
        for model in ["p", "jc69", "k2p"] {
            let (m, _) =
                distance_matrix(&recs(&[("a", "ACGT"), ("b", "ACGT")]), model, "auto").unwrap();
            assert!(m[1] == 0.0 && m[1].is_sign_positive(), "{model}");
        }
    }

    #[test]
    fn saturation_is_decided_on_integer_counts() {
        // P = Q = 1/3: 1 - 2P - Q is exactly 0, which rounded proportions miss.
        let e = distance_matrix(&recs(&[("a", "AAC"), ("b", "GCC")]), "k2p", "auto").unwrap_err();
        assert!(e.0.contains("saturated for k2p"), "{}", e.0);
        let e =
            distance_matrix(&recs(&[("a", "ACGT"), ("b", "CATT")]), "jc69", "auto").unwrap_err();
        assert!(e.0.contains("p = 0.75 is saturated"), "{}", e.0);
    }

    #[test]
    fn protein_u_is_not_threonine() {
        let (m, _) =
            distance_matrix(&recs(&[("a", "MKUW"), ("b", "MKTW")]), "p", "protein").unwrap();
        assert_eq!(m[1], 0.0); // column 3 dropped: 0 of 3 differ
        let (m, _) = distance_matrix(&recs(&[("a", "ACGU"), ("b", "ACGT")]), "p", "auto").unwrap();
        assert_eq!(m[1], 0.0); // nucleotide U is T
    }

    #[test]
    fn errors_match_the_reference_text() {
        let e = distance_matrix(
            &recs(&[("x", "AAAAAAAA"), ("y", "CCCCCCCC")]),
            "jc69",
            "auto",
        )
        .unwrap_err();
        assert_eq!(
            e.0,
            "'x' and 'y': p = 1.0 is saturated for jc69 (needs p < 0.75)"
        );
        let e = distance_matrix(&recs(&[("u1", "ACGT"), ("u2", "ACG")]), "p", "auto").unwrap_err();
        assert!(e
            .0
            .starts_with("sequence 'u2' has length 3, but 'u1' has 4;"));
        let e = distance_matrix(&recs(&[("p1", "MKE"), ("p2", "MKL")]), "k2p", "auto").unwrap_err();
        assert_eq!(
            e.0,
            "model 'k2p' is not available for protein sequences (choose from ('p', 'jc69', 'poisson'))"
        );
        let e =
            distance_matrix(&recs(&[("a\u{1}", "AC"), ("a\u{1}", "AC")]), "p", "auto").unwrap_err();
        assert_eq!(e.0, "duplicate label 'a\\x01'");
        let e = distance_matrix(
            &recs(&[
                ("M\u{fc}ller\u{378}\u{e0001}", "AC"),
                ("M\u{fc}ller\u{378}\u{e0001}", "AC"),
            ]),
            "p",
            "auto",
        )
        .unwrap_err();
        assert_eq!(e.0, "duplicate label 'M\\xfcller\\u0378\\U000e0001'");
        // The alphabet is checked after the record count, as in the reference.
        let e = distance_matrix(&recs(&[("a", "AC")]), "p", "bogus").unwrap_err();
        assert_eq!(e.0, "need at least 2 sequences, got 1");
        let e = distance_matrix(&recs(&[("a", "ACßT"), ("b", "ACGT")]), "p", "auto").unwrap_err();
        assert_eq!(
            e.0,
            "sequence 'a' has '\\xdf' at column 3; sequences must be ASCII"
        );
    }

    #[test]
    fn fasta_uses_ascii_whitespace_and_lf() {
        let r = read_fasta(">a desc\r\nAC GT\r\n>b\rACGA\n").unwrap();
        assert_eq!(r, recs(&[("a", "ACGT"), ("b", "")]));
        let r = read_fasta(">a\u{1c}b\nAC\u{a0}GT\n").unwrap();
        assert_eq!(r[0].0, "a\u{1c}b");
        assert_eq!(r[0].1, "AC\u{a0}GT");
    }
}
