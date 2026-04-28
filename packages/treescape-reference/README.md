# treescape-reference

Slow, readable, pure-Python reference implementations of treescape's tree parsing and layout. **Not** intended for production use — it exists so users of `treescape` can independently verify the EVIDENT trust claims that gate releases of the Rust core.

```bash
pip install treescape-reference
```

```python
from treescape_reference.layout import rectangular_layout
from treescape_reference.newick import parse

tree = parse("(a:1,b:2);")
coords = rectangular_layout(tree)
```

## Why this exists

The Rust core in `treescape-core` is fast and array-based. This package is its readable counterpart: every algorithm is written to be auditable rather than fast. When `treescape` is released, the Rust output must agree with this reference within tolerance — that agreement is one of the EVIDENT claims pinned in the workspace's `evident.yaml`.

If you don't trust the Rust impl, you can install this package and run it yourself.

## Conventions

This package owns the canonical convention choices for tip y-spacing, internal node x-placement, and root x-position. They are documented in `docs/conventions.md` at the workspace root, with explicit notes on where they match or differ from ete3, Biopython.Phylo, and ggtree.

## License

MIT
