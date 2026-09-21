#!/usr/bin/env Rscript
#
# Pairwise sequence distances with R ape, for tests/oracle/test_seq_distances_vs_ape.py:
#   Rscript workflow/scripts/oracle_seq_distance.R <dir-of-fasta>
#
# Every <id>.fasta in <dir> is read; nucleotide files (named *.dna.fasta)
# get dist.dna(model = "raw", "JC69", "K80"; pairwise.deletion = TRUE),
# protein files (*.aa.fasta) get dist.aa(pairwise.deletion = TRUE,
# scaled = TRUE). Output (stdout), one line per matrix:
#   <id>\t<model>\t<n>\t<v11,v12,...> (row-major, 17 significant digits; NaN/Inf as-is)

suppressPackageStartupMessages(library(ape))
args <- commandArgs(trailingOnly = TRUE)
emit <- function(id, model, m) {
  cat(id, "\t", model, "\t", nrow(m), "\t", paste(formatC(as.vector(t(m)), digits = 17, format = "g"), collapse = ","), "\n", sep = "")
}
for (path in sort(list.files(args[1], pattern = "\\.fasta$", full.names = TRUE))) {
  id <- sub("\\.(dna|aa)\\.fasta$", "", basename(path))
  if (grepl("\\.dna\\.fasta$", path)) {
    x <- read.dna(path, format = "fasta")
    for (m in c("raw", "JC69", "K80")) emit(id, m, as.matrix(dist.dna(x, model = m, pairwise.deletion = TRUE)))
  } else {
    x <- as.matrix(read.FASTA(path, type = "AA"))
    emit(id, "aa-p", as.matrix(dist.aa(x, pairwise.deletion = TRUE, scaled = TRUE)))
  }
}
