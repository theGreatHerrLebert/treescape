#!/usr/bin/env Rscript
#
# Emit (node, x, y, is_tip, label) CSV for a Newick fixture's ggtree layout.
#
# Invoked by tests/oracle/test_layout_vs_ggtree.py:
#   Rscript workflow/scripts/oracle_ggtree.R <fixture.nwk>
#
# Output format: stdout CSV with header. Columns:
#   node      integer    ggtree node index
#   x         numeric    cumulative branch length from root
#   y         numeric    pre-order leaf index (top to bottom)
#   is_tip    boolean    TRUE for leaves
#   label     string     tip name (empty for internal nodes)

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1) {
  stop("usage: oracle_ggtree.R <newick-file>")
}

suppressPackageStartupMessages({
  required <- c("ggtree", "ape")
  for (pkg in required) {
    if (!requireNamespace(pkg, quietly = TRUE)) {
      stop(sprintf("missing R package: %s (Bioconductor)", pkg))
    }
  }
  library(ggtree)
  library(ape)
})

tree <- read.tree(args[1])
# ladderize=FALSE: ggtree ladderizes by default (reorders children by clade
# size). treescape's rectangular_layout does not ladderize implicitly — that
# is a separate explicit step. Disabling the default makes the y-coordinate
# convention comparable: ggtree's internal y is then file-order, 1-based,
# top-to-bottom (matching ape's tip.label index). See docs/conventions.md.
p <- ggtree(tree, ladderize = FALSE)
d <- p$data

out <- data.frame(
  node   = d$node,
  x      = d$x,
  y      = d$y,
  is_tip = d$isTip,
  label  = ifelse(is.na(d$label), "", d$label),
  stringsAsFactors = FALSE
)

write.csv(out, row.names = FALSE)
