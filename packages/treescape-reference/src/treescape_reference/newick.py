"""Readable Newick parser and writer.

Companion to ``treescape-core``'s hand-rolled Rust implementation. This
module exists to be obviously correct, not fast — every algorithm
mirrors the Rust version line-for-line so they can be kept in sync.

Used as part of the EVIDENT oracle chain for the
``treescape-newick-roundtrip`` claim. See workspace ``evident.yaml`` and
``cases/treescape.md`` for the trust contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union


@dataclass
class Node:
    name: str = ""
    branch_length: float = 0.0
    children: List["Node"] = field(default_factory=list)
    parent: Optional["Node"] = None

    def is_tip(self) -> bool:
        return not self.children


@dataclass
class Tree:
    root: Optional[Node] = None

    def __len__(self) -> int:
        return sum(1 for _ in self.postorder())

    def postorder(self) -> List[Node]:
        if self.root is None:
            return []
        out: List[Node] = []
        stack: List[Node] = [self.root]
        while stack:
            n = stack.pop()
            out.append(n)
            stack.extend(n.children)
        out.reverse()
        return out

    def topology_hash(self) -> int:
        """Order-invariant Merkle-style hash of structure + names.

        Branch lengths are intentionally excluded.
        """
        cache: dict = {}
        for n in self.postorder():
            child_h = sorted(cache[id(c)] for c in n.children)
            cache[id(n)] = hash((n.name, tuple(child_h)))
        if self.root is None:
            return 0
        return cache[id(self.root)]


# ----- Tokenizer ------------------------------------------------------------

# Tokens are encoded as either a single-char string ('(', ')', ',', ';')
# or a two-tuple ('name', str) / ('len', float).
Token = Union[str, Tuple[str, object]]


_SPECIAL = set("()[],:;'")


def _tokenize(s: str) -> List[Token]:
    tokens: List[Token] = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c in "();,":
            tokens.append(c)
            i += 1
        elif c == ":":
            i += 1
            j = i
            while j < n and (s[j].isdigit() or s[j] in ".-+eE"):
                j += 1
            raw = s[i:j]
            try:
                tokens.append(("len", float(raw)))
            except ValueError as exc:
                raise ValueError(f"invalid number: {raw!r}") from exc
            i = j
        elif c == "'":
            i += 1
            buf: List[str] = []
            closed = False
            while i < n:
                if s[i] == "'":
                    if i + 1 < n and s[i + 1] == "'":
                        buf.append("'")
                        i += 2
                    else:
                        i += 1
                        closed = True
                        break
                else:
                    buf.append(s[i])
                    i += 1
            if not closed:
                raise ValueError("unterminated quoted name")
            tokens.append(("name", "".join(buf)))
        elif c == "[":
            depth = 1
            i += 1
            while i < n and depth > 0:
                if s[i] == "[":
                    depth += 1
                elif s[i] == "]":
                    depth -= 1
                i += 1
            if depth != 0:
                raise ValueError("unterminated comment")
        elif c.isspace():
            i += 1
        else:
            j = i
            while j < n and s[j] not in _SPECIAL and not s[j].isspace():
                j += 1
            tokens.append(("name", s[i:j]))
            i = j
    return tokens


# ----- Parser ---------------------------------------------------------------


def parse(s: str) -> Tree:
    """Parse a Newick string into a :class:`Tree`."""
    tokens = _tokenize(s)
    if not tokens:
        return Tree(root=None)

    stack: List[Node] = []
    current: Optional[Node] = None
    root: Optional[Node] = None

    def attach(child: Node) -> None:
        nonlocal root
        if stack:
            child.parent = stack[-1]
            stack[-1].children.append(child)
        elif root is None:
            root = child

    def new_sibling() -> Node:
        node = Node()
        attach(node)
        return node

    for tok in tokens:
        if tok == "(":
            n = Node()
            attach(n)
            stack.append(n)
            current = None
        elif tok == ")":
            if not stack:
                raise ValueError("unbalanced parenthesis")
            current = stack.pop()
        elif tok == ",":
            current = None
        elif tok == ";":
            if stack:
                raise ValueError("unclosed parenthesis")
            break
        else:
            kind, val = tok  # type: ignore[misc]
            if current is None:
                current = new_sibling()
            if kind == "name":
                current.name = val  # type: ignore[assignment]
            elif kind == "len":
                current.branch_length = val  # type: ignore[assignment]

    return Tree(root=root)


# ----- Writer ---------------------------------------------------------------


def write(tree: Tree) -> str:
    """Serialize a :class:`Tree` to a Newick string. Iterative."""
    if tree.root is None:
        return ";"

    ENTER, BETWEEN, EXIT = 0, 1, 2
    out: List[str] = []
    stack: List[tuple] = [(ENTER, tree.root, 0)]

    while stack:
        action, node, idx = stack.pop()
        if action == ENTER:
            if node.children:
                out.append("(")
                stack.append((BETWEEN, node, 0))
                stack.append((ENTER, node.children[0], 0))
            else:
                stack.append((EXIT, node, 0))
        elif action == BETWEEN:
            nxt = idx + 1
            if nxt < len(node.children):
                out.append(",")
                stack.append((BETWEEN, node, nxt))
                stack.append((ENTER, node.children[nxt], 0))
            else:
                out.append(")")
                stack.append((EXIT, node, 0))
        else:  # EXIT
            out.append(_write_name(node.name))
            if node is not tree.root:
                out.append(":")
                out.append(_write_float(node.branch_length))

    out.append(";")
    return "".join(out)


def _write_name(name: str) -> str:
    if not name:
        return ""
    needs_quotes = any(c in _SPECIAL or c.isspace() for c in name)
    if needs_quotes:
        return "'" + name.replace("'", "''") + "'"
    return name


def _write_float(f: float) -> str:
    """Shortest round-trip representation. ``repr`` matches Rust's ``{:?}``
    for the values we round-trip in fixtures."""
    return repr(f)


__all__ = ["Node", "Tree", "parse", "write"]
