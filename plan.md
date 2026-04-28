Phylogenetic Tree Plotting in Python — Plan

Vision

Build a Python-native library for fast, flexible, and beautiful phylogenetic tree visualization that is as easy to use as possible while supporting advanced annotation workflows.

This is not just a tree viewer. It is a declarative system for annotated biological tree figures.

⸻

Core Principles

* Simple things should be trivial
* Advanced use cases should remain possible
* Defaults should look good
* Metadata is a first-class citizen
* Output should be publication-ready

⸻

1. Internal Tree Model

Support:

* Newick
* Nexus
* PhyloXML
* JSON import/export
* Branch lengths
* Support values
* Node metadata
* Tip metadata
* Clade metadata

Design goal:

* Interoperate with existing libraries (Biopython, ETE, DendroPy)
* Avoid reinventing core tree parsing unnecessarily

⸻

2. Grammar of Tree Graphics

Introduce a composable, declarative API:

(
    TreePlot(tree)
    .layout("rectangular")
    .tips(label="species")
    .branches(color_by="clade")
    .nodes(size_by="support")
    .clade("Mammalia").highlight()
    .metadata_bar(df, columns=["host", "country"])
    .save("tree.svg")
)

Goals:

* Clear mental model
* Layered transformations
* Composable operations

⸻

3. Layout Engine

Minimum layouts:

* Rectangular phylogram
* Rectangular cladogram
* Circular
* Radial/fan

Future:

* Unrooted
* Collapsed clades
* Subtree extraction
* Ladderization

Key challenge:

* Label collision avoidance
* Automatic spacing and scaling

⸻

4. Metadata-First Annotation

Core concept:

plot = TreePlot(tree).join_metadata(df, on="tip_name")

Supported mappings:

* Tip colors
* Branch colors
* Node size/color
* Clade highlighting
* Heatmap tracks
* Bar plots
* Symbols/icons
* Support labels
* Group backgrounds

This is essential for real biological workflows.

⸻

5. Beautiful Defaults

Default behavior:

TreePlot("tree.nwk").save("tree.svg")

Should produce:

* Clean layout
* Readable labels
* Balanced spacing
* Publication-ready output

Requirements:

* Sensible font scaling
* Automatic margins
* Good color palettes
* SVG/PDF export quality

⸻

6. Rendering Architecture

Avoid tight coupling to matplotlib.

Proposed pipeline:

Tree + metadata
      ↓
Layout engine
      ↓
Scene graph
      ↓
Renderer (SVG / PDF / PNG / HTML)

Benefits:

* Backend flexibility
* Clean separation of concerns
* Easier future interactivity

⸻

7. Performance Targets

Target scales:

* 100 tips → instant
* 1,000 tips → smooth
* 10,000 tips → usable with optimizations
* 100,000 tips → collapsed/interactive only

Approach:

* Array-based internal representation
* Avoid deep recursion
* Lazy rendering where possible

⸻

8. Interfaces

Python API

TreePlot("tree.nwk")

CLI

treeplot tree.nwk --metadata meta.csv --layout circular --out tree.svg

Jupyter Support

* Inline rendering
* Interactive exploration (future)

⸻

9. Presets

Provide opinionated presets:

TreePlot(tree).preset("paper")
TreePlot(tree).preset("taxonomy")
TreePlot(tree).preset("bootstrap")
TreePlot(tree).preset("large_tree")

Goal:

* Reduce configuration burden
* Encourage consistent visual styles

⸻

10. MVP Scope

First version should include:

1. Newick parsing
2. Rectangular + circular layouts
3. Robust tip labeling
4. Metadata joins
5. Styling by metadata
6. Clade highlighting
7. SVG/PDF export
8. Default theme

⸻

11. Long-Term Features

* Interactive web viewer
* Plugin system
* Animation (e.g., evolutionary timelines)
* Integration with analysis pipelines
* Large-tree navigation tools

⸻

Summary

The goal is to close the gap in Python by building a tool that:

* Combines ease of use with flexibility
* Treats trees as data + annotations
* Produces high-quality figures by default

The real value lies not in drawing trees, but in making annotated, interpretable biological figures easy to createPhylogenetic Tree Plotting in Python — Plan

Vision

Build a Python-native library for fast, flexible, and beautiful phylogenetic tree visualization that is as easy to use as possible while supporting advanced annotation workflows.

This is not just a tree viewer. It is a declarative system for annotated biological tree figures.

⸻

Core Principles

* Simple things should be trivial
* Advanced use cases should remain possible
* Defaults should look good
* Metadata is a first-class citizen
* Output should be publication-ready

⸻

1. Internal Tree Model

Support:

* Newick
* Nexus
* PhyloXML
* JSON import/export
* Branch lengths
* Support values
* Node metadata
* Tip metadata
* Clade metadata

Design goal:

* Interoperate with existing libraries (Biopython, ETE, DendroPy)
* Avoid reinventing core tree parsing unnecessarily

⸻

2. Grammar of Tree Graphics

Introduce a composable, declarative API:

(
    TreePlot(tree)
    .layout("rectangular")
    .tips(label="species")
    .branches(color_by="clade")
    .nodes(size_by="support")
    .clade("Mammalia").highlight()
    .metadata_bar(df, columns=["host", "country"])
    .save("tree.svg")
)

Goals:

* Clear mental model
* Layered transformations
* Composable operations

⸻

3. Layout Engine

Minimum layouts:

* Rectangular phylogram
* Rectangular cladogram
* Circular
* Radial/fan

Future:

* Unrooted
* Collapsed clades
* Subtree extraction
* Ladderization

Key challenge:

* Label collision avoidance
* Automatic spacing and scaling

⸻

4. Metadata-First Annotation

Core concept:

plot = TreePlot(tree).join_metadata(df, on="tip_name")

Supported mappings:

* Tip colors
* Branch colors
* Node size/color
* Clade highlighting
* Heatmap tracks
* Bar plots
* Symbols/icons
* Support labels
* Group backgrounds

This is essential for real biological workflows.

⸻

5. Beautiful Defaults

Default behavior:

TreePlot("tree.nwk").save("tree.svg")

Should produce:

* Clean layout
* Readable labels
* Balanced spacing
* Publication-ready output

Requirements:

* Sensible font scaling
* Automatic margins
* Good color palettes
* SVG/PDF export quality

⸻

6. Rendering Architecture

Avoid tight coupling to matplotlib.

Proposed pipeline:

Tree + metadata
      ↓
Layout engine
      ↓
Scene graph
      ↓
Renderer (SVG / PDF / PNG / HTML)

Benefits:

* Backend flexibility
* Clean separation of concerns
* Easier future interactivity

⸻

7. Performance Targets

Target scales:

* 100 tips → instant
* 1,000 tips → smooth
* 10,000 tips → usable with optimizations
* 100,000 tips → collapsed/interactive only

Approach:

* Array-based internal representation
* Avoid deep recursion
* Lazy rendering where possible

⸻

8. Interfaces

Python API

TreePlot("tree.nwk")

CLI

treeplot tree.nwk --metadata meta.csv --layout circular --out tree.svg

Jupyter Support

* Inline rendering
* Interactive exploration (future)

⸻

9. Presets

Provide opinionated presets:

TreePlot(tree).preset("paper")
TreePlot(tree).preset("taxonomy")
TreePlot(tree).preset("bootstrap")
TreePlot(tree).preset("large_tree")

Goal:

* Reduce configuration burden
* Encourage consistent visual styles

⸻

10. MVP Scope

First version should include:

1. Newick parsing
2. Rectangular + circular layouts
3. Robust tip labeling
4. Metadata joins
5. Styling by metadata
6. Clade highlighting
7. SVG/PDF export
8. Default theme

⸻

11. Long-Term Features

* Interactive web viewer
* Plugin system
* Animation (e.g., evolutionary timelines)
* Integration with analysis pipelines
* Large-tree navigation tools

⸻

Summary

The goal is to close the gap in Python by building a tool that:

* Combines ease of use with flexibility
* Treats trees as data + annotations
* Produces high-quality figures by default

The real value lies not in drawing trees, but in making annotated, interpretable biological figures easy to create..
