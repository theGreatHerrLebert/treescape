# treescape-connector

The compiled core of [treescape](https://pypi.org/project/treescape/): Rust tree parsing, layout, tree building and SVG rendering, exposed to Python through PyO3. It is installed automatically as a dependency of `treescape`; use `treescape` (`from treescape import TreePlot`), not this package, directly.

One wheel per platform, built against CPython's stable ABI (Python ≥ 3.11): Linux (manylinux2014, x86-64 and aarch64), macOS (arm64 and x86-64) and Windows (x86-64). Every wheel is tested installed before release: it must reproduce treescape's gallery byte for byte.

- Documentation: <https://thegreatherrlebert.github.io/treescape/>
- Source and license: <https://github.com/theGreatHerrLebert/treescape> (MIT; the embedded DejaVu Sans font is under the Bitstream Vera and Arev licenses, shipped in the wheel's `.dist-info/licenses/`).
