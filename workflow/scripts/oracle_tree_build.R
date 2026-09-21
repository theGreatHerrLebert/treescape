#!/usr/bin/env Rscript
#
# Build trees from distance matrices with R's reference implementations.
# Invoked by tests/oracle/test_tree_build_vs_r.py:
#   Rscript workflow/scripts/oracle_tree_build.R <nj|upgma> <dir-of-tsv>
#
# Input: every <id>.tsv in <dir> (first line: tab-separated labels, then
# n rows of n numbers, written with 17 significant digits).
# Output (stdout): one line per matrix, "<id>\t<newick>", with branch
# lengths written at 17 significant digits so nothing is lost.
#   nj    -> ape::nj            (unrooted; compared as unrooted)
#   upgma -> phangorn::upgma    (rooted, ultrametric)

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2 || !(args[1] %in% c("nj", "upgma"))) {
  stop("usage: oracle_tree_build.R <nj|upgma> <dir-of-tsv>")
}
method <- args[1]
suppressPackageStartupMessages({
  library(ape)
  if (method == "upgma") library(phangorn)
})

for (path in sort(list.files(args[2], pattern = "\\.tsv$", full.names = TRUE))) {
  lines <- readLines(path)
  labels <- strsplit(lines[1], "\t", fixed = TRUE)[[1]]
  m <- do.call(rbind, lapply(strsplit(lines[-1], "\t", fixed = TRUE), as.numeric))
  dimnames(m) <- list(labels, labels)
  d <- as.dist(m)
  tree <- if (method == "nj") nj(d) else upgma(d)
  id <- sub("\\.tsv$", "", basename(path))
  cat(id, "\t", write.tree(tree, digits = 17), "\n", sep = "")
}
