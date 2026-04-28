"""treescape — declarative phylogenetic tree visualization.

The user-facing entry point is :class:`TreePlot`. Implementation lands in
Phase 4; this skeleton exists so the package layout validates end to end.
"""

from .plot import TreePlot, TreescapeStyleWarning

__all__ = ["TreePlot", "TreescapeStyleWarning"]
__version__ = "0.1.0"
