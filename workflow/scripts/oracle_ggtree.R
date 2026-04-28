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
if (length(args) < 1 || length(args) > 2) {
  stop("usage: oracle_ggtree.R <newick-file> [--circular]")
}
fixture <- args[1]
circular <- length(args) == 2 && args[2] == "--circular"

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

tree <- read.tree(fixture)

# ladderize=FALSE: ggtree ladderizes by default (reorders children by clade
# size). treescape's layouts do not ladderize implicitly — that is a separate
# explicit step. Disabling the default makes the coordinate conventions
# comparable across both rectangular and circular outputs.
if (circular) {
  p <- ggtree(tree, layout = "circular", ladderize = FALSE)
} else {
  p <- ggtree(tree, ladderize = FALSE)
}
d <- p$data

if (circular) {
  # For ggtree's circular layout, p$data$x stays as the tree's
  # cumulative branch length (= treescape r) and p$data$angle gives
  # the per-node angle in DEGREES. The polar (r, θ) we want is
  # therefore (x, angle * π / 180). This is a different code path
  # than the rectangular case which reads p$data$x/y as plot coords.
  # Convention divergences vs treescape (documented in
  # docs/conventions.md):
  #   * Direction: ggtree sweeps CCW, treescape CW; oracle test
  #     applies θ_ggtree = π − θ_ours.
  #   * Internal-node angle: ggtree linear mean of children, treescape
  #     wrap-aware vector mean. Diverges only for diametrically
  #     opposed children; oracle test compares tips only to sidestep.
  out <- data.frame(
    node   = d$node,
    r      = d$x,
    theta  = d$angle * pi / 180,
    is_tip = d$isTip,
    label  = ifelse(is.na(d$label), "", d$label),
    stringsAsFactors = FALSE
  )
} else {
  out <- data.frame(
    node   = d$node,
    x      = d$x,
    y      = d$y,
    is_tip = d$isTip,
    label  = ifelse(is.na(d$label), "", d$label),
    stringsAsFactors = FALSE
  )
}

write.csv(out, row.names = FALSE)
