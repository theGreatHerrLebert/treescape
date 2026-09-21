"""treescape — declarative phylogenetic tree visualization.

The user-facing entry point is :class:`TreePlot`. Implementation lands in
Phase 4; this skeleton exists so the package layout validates end to end.
"""

from . import distances
from .distances import TreescapeSequenceWarning
from .plot import TreePlot, TreescapeStyleWarning

__all__ = ["TreePlot", "TreescapeSequenceWarning", "TreescapeStyleWarning", "distances"]
__version__ = "0.7.0"
