# Third-party notices

treescape is MIT-licensed (see [LICENSE](LICENSE)). This file lists what
it **bundles**, what it **links**, what data it **reproduces**, and what
it only **tests against**, with each upstream license.

## Bundled and redistributed

### DejaVu Sans (font)

`DejaVuSans.ttf` is embedded at compile time into `treescape-render`
(and therefore into the Python and Julia connector libraries) for
tip-label measurement, and shipped as a file with `treescape-reference`.
It is the unmodified upstream font from <https://dejavu-fonts.github.io/>.

License: **Bitstream Vera Fonts License**, plus the **Arev Fonts
License** for glyphs DejaVu imported from the Arev fonts (DejaVu's own
changes are public domain). The full notice, which must accompany every
copy, is the font's own license text (its name ID 13) and is in
[`treescape-render/src/fonts/LICENSE.DejaVu.txt`](treescape-render/src/fonts/LICENSE.DejaVu.txt)
and [`packages/treescape-reference/src/treescape_reference/fonts/LICENSE.DejaVu.txt`](packages/treescape-reference/src/treescape_reference/fonts/LICENSE.DejaVu.txt).
The `treescape_connector` wheel ships it in `.dist-info/licenses/`
(declared as `MIT AND Bitstream-Vera`), and the Rust crates that embed
the font (`treescape-render` and both connectors) declare the same
license expression. SVG output references the font by family name only;
no glyph data is written into figures.

## Reproduced data

- **viridis** — treescape's 11-keystop colormap samples matplotlib's
  viridis by Stéfan van der Walt and Nathaniel Smith, released under
  **CC0** (<https://bids.github.io/colormap/>). The interpolated LUT is
  treescape's own and is not byte-identical to matplotlib's.
- **Tableau 10** — the default categorical palette uses the ten hex
  values of the Tableau 10 palette designed by Maureen Stone for Tableau
  Software (2016). Only the color values are used.

## Linked libraries

### Rust (compiled into the connector libraries)

Generated from `cargo metadata` (non-workspace packages). All are
permissively licensed; none is copyleft.

| Crate | Version | License |
|---|---|---|
| [allocator-api2](https://github.com/zakarumych/allocator-api2) | 0.2.21 | MIT OR Apache-2.0 |
| [autocfg](https://github.com/cuviper/autocfg) | 1.5.0 | Apache-2.0 OR MIT |
| [byteorder](https://github.com/BurntSushi/byteorder) | 1.5.0 | Unlicense OR MIT |
| [cfg-if](https://github.com/rust-lang/cfg-if) | 1.0.4 | MIT OR Apache-2.0 |
| [equivalent](https://github.com/indexmap-rs/equivalent) | 1.0.2 | Apache-2.0 OR MIT |
| [foldhash](https://github.com/orlp/foldhash) | 0.1.5 | Zlib |
| [fontdue](https://github.com/mooman219/fontdue) | 0.9.3 | MIT OR Apache-2.0 OR Zlib |
| [fxhash](https://github.com/cbreeden/fxhash) | 0.2.1 | Apache-2.0/MIT |
| [hashbrown](https://github.com/rust-lang/hashbrown) | 0.15.5 | MIT OR Apache-2.0 |
| [heck](https://github.com/withoutboats/heck) | 0.5.0 | MIT OR Apache-2.0 |
| [indoc](https://github.com/dtolnay/indoc) | 2.0.7 | MIT OR Apache-2.0 |
| [libc](https://github.com/rust-lang/libc) | 0.2.186 | MIT OR Apache-2.0 |
| [memoffset](https://github.com/Gilnaa/memoffset) | 0.9.1 | MIT |
| [once_cell](https://github.com/matklad/once_cell) | 1.21.4 | MIT OR Apache-2.0 |
| [portable-atomic](https://github.com/taiki-e/portable-atomic) | 1.13.1 | Apache-2.0 OR MIT |
| [proc-macro2](https://github.com/dtolnay/proc-macro2) | 1.0.106 | MIT OR Apache-2.0 |
| [pyo3](https://github.com/pyo3/pyo3) | 0.23.5 | MIT OR Apache-2.0 |
| [pyo3-build-config](https://github.com/pyo3/pyo3) | 0.23.5 | MIT OR Apache-2.0 |
| [pyo3-ffi](https://github.com/pyo3/pyo3) | 0.23.5 | MIT OR Apache-2.0 |
| [pyo3-macros](https://github.com/pyo3/pyo3) | 0.23.5 | MIT OR Apache-2.0 |
| [pyo3-macros-backend](https://github.com/pyo3/pyo3) | 0.23.5 | MIT OR Apache-2.0 |
| [quote](https://github.com/dtolnay/quote) | 1.0.45 | MIT OR Apache-2.0 |
| [rustversion](https://github.com/dtolnay/rustversion) | 1.0.22 | MIT OR Apache-2.0 |
| [syn](https://github.com/dtolnay/syn) | 2.0.117 | MIT OR Apache-2.0 |
| [target-lexicon](https://github.com/bytecodealliance/target-lexicon) | 0.12.16 | Apache-2.0 WITH LLVM-exception |
| [ttf-parser](https://github.com/RazrFalcon/ttf-parser) | 0.21.1 | MIT OR Apache-2.0 |
| [unicode-ident](https://github.com/dtolnay/unicode-ident) | 1.0.24 | (MIT OR Apache-2.0) AND Unicode-3.0 |
| [unindent](https://github.com/dtolnay/indoc) | 0.2.4 | MIT OR Apache-2.0 |

### Python runtime

| Package | License | Used by |
|---|---|---|
| [polars](https://github.com/pola-rs/polars) | MIT | `treescape` (`join_metadata`), `treescape-reference` |
| [fontTools](https://github.com/fonttools/fonttools) | MIT | `treescape-reference` (glyph advance widths) |

### Julia runtime

| Package | License | Used by |
|---|---|---|
| [Tables.jl](https://github.com/JuliaData/Tables.jl) | MIT | `Treescape.jl` (`join_metadata!`) |
| [Preferences.jl](https://github.com/JuliaPackaging/Preferences.jl) | MIT | `Treescape.jl` (library location) |

## Verification oracles (test-only; not linked, not redistributed)

These tools are imported or called only by the test suite under
`tests/oracle/` to check treescape's output. None is a dependency of
the distributed packages, and no code from them is copied into
treescape.

| Tool | License | Checks |
|---|---|---|
| [ete3](https://github.com/etetoolkit/ete) | GPL-3.0 | rectangular and circular layout, ladderize order |
| [Biopython](https://github.com/biopython/biopython) (Bio.Phylo) | Biopython License / BSD-3-Clause | Newick parsing, rectangular layout |
| [ggtree](https://bioconductor.org/packages/ggtree/) (R, Bioconductor) | Artistic-2.0 | rectangular and circular layout (release tier) |
| [Hypothesis](https://github.com/HypothesisWorks/hypothesis) | MPL-2.0 | property-based test generation |
| [Miri](https://github.com/rust-lang/miri) | MIT OR Apache-2.0 | undefined-behavior checks of the C ABI tests |
