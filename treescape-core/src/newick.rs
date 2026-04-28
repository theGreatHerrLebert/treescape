//! Hand-rolled Newick parser and writer.
//!
//! Grammar (simplified):
//! ```text
//! tree     = subtree ";"
//! subtree  = leaf | internal
//! leaf     = name [":" branch_length]
//! internal = "(" subtree ("," subtree)* ")" [name] [":" branch_length]
//! name     = unquoted | quoted | empty
//! ```
//!
//! Bracketed comments and NHX annotations (`[&&NHX:...]`) are consumed
//! and discarded in v0.1 — the `nhx_comments.nwk` fixture documents that
//! NHX preservation is a v0.2 deliverable.
//!
//! Parser and writer are both iterative (explicit stack, not Rust call
//! stack) so pathological-depth ladder trees do not blow the stack.

use crate::tree::{NodeId, Tree};

#[derive(Debug, Clone, PartialEq)]
pub enum NewickError {
    UnbalancedParen,
    UnclosedParen,
    UnterminatedQuote,
    UnterminatedComment,
    InvalidNumber(String),
    MissingSemicolon,
    TrailingContent,
    MultipleRoots,
}

impl std::fmt::Display for NewickError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::UnbalancedParen => write!(f, "unbalanced parenthesis"),
            Self::UnclosedParen => write!(f, "unclosed parenthesis"),
            Self::UnterminatedQuote => write!(f, "unterminated quoted name"),
            Self::UnterminatedComment => write!(f, "unterminated comment"),
            Self::InvalidNumber(s) => write!(f, "invalid number: {}", s),
            Self::MissingSemicolon => write!(f, "missing trailing semicolon"),
            Self::TrailingContent => write!(f, "trailing content after semicolon"),
            Self::MultipleRoots => write!(f, "multiple top-level roots; expected exactly one"),
        }
    }
}

impl std::error::Error for NewickError {}

#[derive(Debug, Clone, PartialEq)]
enum Token {
    Open,
    Close,
    Comma,
    Semi,
    Name(String),
    BranchLen(f64),
}

fn tokenize(input: &str) -> Result<Vec<Token>, NewickError> {
    let bytes: Vec<char> = input.chars().collect();
    let mut tokens = Vec::new();
    let mut i = 0;
    while i < bytes.len() {
        let c = bytes[i];
        match c {
            '(' => {
                tokens.push(Token::Open);
                i += 1;
            }
            ')' => {
                tokens.push(Token::Close);
                i += 1;
            }
            ',' => {
                tokens.push(Token::Comma);
                i += 1;
            }
            ';' => {
                tokens.push(Token::Semi);
                i += 1;
            }
            ':' => {
                i += 1;
                let start = i;
                while i < bytes.len() {
                    let cc = bytes[i];
                    let is_num = cc.is_ascii_digit()
                        || cc == '.'
                        || cc == '-'
                        || cc == '+'
                        || cc == 'e'
                        || cc == 'E';
                    if !is_num {
                        break;
                    }
                    i += 1;
                }
                let raw: String = bytes[start..i].iter().collect();
                let v: f64 = raw
                    .parse()
                    .map_err(|_| NewickError::InvalidNumber(raw.clone()))?;
                tokens.push(Token::BranchLen(v));
            }
            '\'' => {
                i += 1;
                let mut buf = String::new();
                let mut closed = false;
                while i < bytes.len() {
                    if bytes[i] == '\'' {
                        if i + 1 < bytes.len() && bytes[i + 1] == '\'' {
                            buf.push('\'');
                            i += 2;
                        } else {
                            i += 1;
                            closed = true;
                            break;
                        }
                    } else {
                        buf.push(bytes[i]);
                        i += 1;
                    }
                }
                if !closed {
                    return Err(NewickError::UnterminatedQuote);
                }
                tokens.push(Token::Name(buf));
            }
            '[' => {
                i += 1;
                let mut depth = 1;
                while i < bytes.len() && depth > 0 {
                    match bytes[i] {
                        '[' => depth += 1,
                        ']' => depth -= 1,
                        _ => {}
                    }
                    i += 1;
                }
                if depth != 0 {
                    return Err(NewickError::UnterminatedComment);
                }
            }
            c if c.is_whitespace() => {
                i += 1;
            }
            _ => {
                let start = i;
                while i < bytes.len() {
                    let cc = bytes[i];
                    if matches!(cc, '(' | ')' | '[' | ']' | ',' | ':' | ';' | '\'') || cc.is_whitespace() {
                        break;
                    }
                    i += 1;
                }
                let raw: String = bytes[start..i].iter().collect();
                tokens.push(Token::Name(raw));
            }
        }
    }
    Ok(tokens)
}

pub fn parse(input: &str) -> Result<Tree, NewickError> {
    let tokens = tokenize(input)?;
    let mut tree = Tree::default();
    let mut stack: Vec<NodeId> = Vec::new();
    let mut current: Option<NodeId> = None;
    let mut seen_semi = false;

    let attach_to_parent = |tree: &mut Tree, stack: &[NodeId], child: NodeId| {
        if let Some(&p) = stack.last() {
            tree.parent[child] = Some(p);
            tree.children[p].push(child);
        }
    };

    let new_sibling = |tree: &mut Tree, stack: &[NodeId]| -> NodeId {
        let id = tree.add_node();
        attach_to_parent(tree, stack, id);
        id
    };

    let mut iter = tokens.into_iter();
    while let Some(tok) = iter.next() {
        match tok {
            Token::Open => {
                let id = tree.add_node();
                attach_to_parent(&mut tree, &stack, id);
                stack.push(id);
                current = None;
            }
            Token::Close => {
                let id = stack.pop().ok_or(NewickError::UnbalancedParen)?;
                current = Some(id);
            }
            Token::Comma => {
                current = None;
            }
            Token::Semi => {
                if !stack.is_empty() {
                    return Err(NewickError::UnclosedParen);
                }
                if iter.next().is_some() {
                    return Err(NewickError::TrailingContent);
                }
                seen_semi = true;
                break;
            }
            Token::Name(s) => {
                let id = current.unwrap_or_else(|| new_sibling(&mut tree, &stack));
                tree.name[id] = s;
                current = Some(id);
            }
            Token::BranchLen(v) => {
                let id = current.unwrap_or_else(|| new_sibling(&mut tree, &stack));
                tree.branch_len[id] = v;
                current = Some(id);
            }
        }
    }

    if tree.parent.is_empty() {
        // Empty input (no tokens) or just `;`. Both are tolerated as
        // empty trees. A non-empty input that produced no nodes (e.g.
        // only whitespace) is also empty.
        if !seen_semi && !tree.parent.is_empty() {
            return Err(NewickError::MissingSemicolon);
        }
        return Ok(tree);
    }

    if !seen_semi {
        return Err(NewickError::MissingSemicolon);
    }

    let root_count = tree.parent.iter().filter(|p| p.is_none()).count();
    if root_count != 1 {
        return Err(NewickError::MultipleRoots);
    }
    tree.root = Some(0);
    tree.finalize();
    Ok(tree)
}

pub fn write(tree: &Tree) -> String {
    let mut buf = String::new();
    let Some(root) = tree.root else {
        buf.push(';');
        return buf;
    };

    enum Frame {
        Enter(NodeId),
        Between(NodeId, usize),
        Exit(NodeId),
    }

    let mut stack: Vec<Frame> = vec![Frame::Enter(root)];

    while let Some(frame) = stack.pop() {
        match frame {
            Frame::Enter(id) => {
                if !tree.children[id].is_empty() {
                    buf.push('(');
                    stack.push(Frame::Between(id, 0));
                    stack.push(Frame::Enter(tree.children[id][0]));
                } else {
                    stack.push(Frame::Exit(id));
                }
            }
            Frame::Between(id, child_idx) => {
                let next = child_idx + 1;
                if next < tree.children[id].len() {
                    buf.push(',');
                    stack.push(Frame::Between(id, next));
                    stack.push(Frame::Enter(tree.children[id][next]));
                } else {
                    buf.push(')');
                    stack.push(Frame::Exit(id));
                }
            }
            Frame::Exit(id) => {
                write_name(&tree.name[id], &mut buf);
                if Some(id) != tree.root {
                    buf.push(':');
                    write_float(tree.branch_len[id], &mut buf);
                }
            }
        }
    }
    buf.push(';');
    buf
}

fn write_name(name: &str, buf: &mut String) {
    if name.is_empty() {
        return;
    }
    let needs_quotes = name
        .chars()
        .any(|c| matches!(c, '(' | ')' | '[' | ']' | ',' | ':' | ';' | '\'') || c.is_whitespace());
    if needs_quotes {
        buf.push('\'');
        for c in name.chars() {
            if c == '\'' {
                buf.push('\'');
                buf.push('\'');
            } else {
                buf.push(c);
            }
        }
        buf.push('\'');
    } else {
        buf.push_str(name);
    }
}

fn write_float(f: f64, buf: &mut String) {
    // Rust's Debug for f64 is locale-independent and gives the shortest
    // round-trip representation: 1.0 -> "1.0", 0.1 -> "0.1", -0.1 -> "-0.1".
    buf.push_str(&format!("{:?}", f));
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tree_eq_structural(a: &Tree, b: &Tree) -> bool {
        if a.len() != b.len() {
            return false;
        }
        if a.topology_hash() != b.topology_hash() {
            return false;
        }
        // Compare branch lengths sorted by position-in-postorder + name.
        // Since tree IDs may differ, line them up via postorder of each.
        let pa = a.postorder();
        let pb = b.postorder();
        if pa.len() != pb.len() {
            return false;
        }
        // Both trees should walk in identical structural order if identical.
        for (&ia, &ib) in pa.iter().zip(pb.iter()) {
            if a.name[ia] != b.name[ib] {
                return false;
            }
            if (a.branch_len[ia] - b.branch_len[ib]).abs() > f64::EPSILON {
                return false;
            }
        }
        true
    }

    fn roundtrip_ok(s: &str) -> bool {
        let t1 = parse(s).expect("parse 1");
        let s2 = write(&t1);
        let t2 = parse(&s2).expect("parse 2");
        tree_eq_structural(&t1, &t2)
    }

    #[test]
    fn parses_two_tip() {
        let t = parse("(a:1.0,b:2.0);").unwrap();
        assert_eq!(t.len(), 3);
        assert_eq!(t.root, Some(0));
        assert_eq!(t.children[0], vec![1, 2]);
        assert_eq!(t.name[1], "a");
        assert_eq!(t.name[2], "b");
        assert_eq!(t.branch_len[1], 1.0);
        assert_eq!(t.branch_len[2], 2.0);
        assert!(t.is_tip[1] && t.is_tip[2]);
        assert!(!t.is_tip[0]);
    }

    #[test]
    fn parses_balanced_4() {
        let t = parse("((a:1.0,b:1.0):1.0,(c:1.0,d:1.0):1.0);").unwrap();
        assert_eq!(t.len(), 7);
        let tips: Vec<_> = (0..t.len()).filter(|&i| t.is_tip[i]).collect();
        assert_eq!(tips.len(), 4);
    }

    #[test]
    fn parses_quoted_names() {
        let t = parse("('Homo sapiens':1.0,'Pan paniscus':1.0);").unwrap();
        assert_eq!(t.name[1], "Homo sapiens");
        assert_eq!(t.name[2], "Pan paniscus");
    }

    #[test]
    fn parses_negative_branch() {
        let t = parse("(a:-0.1,b:0.5);").unwrap();
        assert_eq!(t.branch_len[1], -0.1);
        assert_eq!(t.branch_len[2], 0.5);
    }

    #[test]
    fn parses_trifurcation() {
        let t = parse("(a:1.0,b:1.0,c:1.0);").unwrap();
        assert_eq!(t.children[0], vec![1, 2, 3]);
    }

    #[test]
    fn parses_nhx_comment_dropped() {
        let t = parse("(a:1.0[&&NHX:S=human],b:1.0);").unwrap();
        assert_eq!(t.name[1], "a");
        assert_eq!(t.branch_len[1], 1.0);
    }

    #[test]
    fn writes_balanced_4() {
        let s = "((a:1.0,b:1.0):1.0,(c:1.0,d:1.0):1.0);";
        let t = parse(s).unwrap();
        let s2 = write(&t);
        assert_eq!(s, s2);
    }

    #[test]
    fn writes_quoted_names() {
        let s = "('Homo sapiens':1.0,'Pan paniscus':1.0);";
        let t = parse(s).unwrap();
        let s2 = write(&t);
        assert_eq!(s, s2);
    }

    #[test]
    fn roundtrip_canonical_fixtures() {
        for s in [
            "(a:1.0,b:2.0);",
            "((a:1.0,b:1.0):1.0,(c:1.0,d:1.0):1.0);",
            "((((a:1.0,b:1.0):1.0,c:2.0):1.0,d:3.0):1.0,e:4.0);",
            "('Homo sapiens':1.0,'Pan paniscus':1.0);",
            "(a:-0.1,b:0.5);",
            "(a:1.0,b:1.0,c:1.0);",
        ] {
            assert!(roundtrip_ok(s), "round-trip failed for: {s}");
        }
    }

    #[test]
    fn topology_hash_invariant_to_child_order() {
        // Same structure, swapped sibling order
        let t1 = parse("((a:1.0,b:1.0):1.0,(c:1.0,d:1.0):1.0);").unwrap();
        let t2 = parse("((b:1.0,a:1.0):1.0,(d:1.0,c:1.0):1.0);").unwrap();
        let t3 = parse("((c:1.0,d:1.0):1.0,(a:1.0,b:1.0):1.0);").unwrap();
        assert_eq!(t1.topology_hash(), t2.topology_hash());
        assert_eq!(t1.topology_hash(), t3.topology_hash());
    }

    #[test]
    fn topology_hash_distinguishes_topology() {
        let t1 = parse("((a,b),c);").unwrap();
        let t2 = parse("((a,c),b);").unwrap();
        assert_ne!(t1.topology_hash(), t2.topology_hash());
    }

    #[test]
    fn errors_on_unbalanced() {
        assert!(matches!(parse("(a,b;").unwrap_err(), NewickError::UnclosedParen));
        assert!(matches!(parse("a,b);").unwrap_err(), NewickError::UnbalancedParen));
    }

    #[test]
    fn errors_on_unterminated_quote() {
        assert!(matches!(
            parse("('a:1.0);").unwrap_err(),
            NewickError::UnterminatedQuote
        ));
    }

    #[test]
    fn errors_on_trailing_content() {
        assert!(matches!(
            parse("(a:1.0);(b:1.0);").unwrap_err(),
            NewickError::TrailingContent
        ));
    }

    #[test]
    fn errors_on_missing_semicolon() {
        assert!(matches!(
            parse("(a:1.0,b:1.0)").unwrap_err(),
            NewickError::MissingSemicolon
        ));
    }

    #[test]
    fn errors_on_multiple_roots() {
        assert!(matches!(
            parse("a,b;").unwrap_err(),
            NewickError::MultipleRoots
        ));
    }

    #[test]
    fn empty_input_is_empty_tree() {
        let t = parse("").unwrap();
        assert!(t.is_empty());
        let t = parse(";").unwrap();
        assert!(t.is_empty());
    }
}
