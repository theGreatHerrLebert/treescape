"""Fetch the primate cytochrome b alignment used by the docs examples.

    python scripts/fetch_primates_cytb.py            # writes tests/fixtures/sequences/primates_cytb.fasta

For each of the 11 species in ``tests/fixtures/trees/medium/primates.nwk``,
the annotated CYTB coding sequence of its RefSeq mitochondrial genome is
fetched from NCBI (E-utilities, ``rettype=fasta_cds_na``). The alignment
is codons 1-379 (1137 nt) of each CDS: the New World monkeys' CYTB is 379
codons plus a stop codon, the others' 380 codons plus an incomplete stop,
so the full proteins differ by one C-terminal residue. Up to codon 379 the
translations (vertebrate mitochondrial code) line up without gaps: the
script checks for internal stop codons, the conserved W at codon 379 and
that the last 40 residues are in register, and that the output matches
``EXPECTED_SHA256``.

GenBank/RefSeq data carry no use restrictions (NCBI's policy); the
accessions are listed here and in the FASTA headers.
"""

from __future__ import annotations

import hashlib
import re
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "tests" / "fixtures" / "sequences" / "primates_cytb.fasta"
CODONS = 379

# Species (tip names of primates.nwk) -> RefSeq mitochondrial genome.
ACCESSIONS = {
    "Homo_sapiens": "NC_012920.1",
    "Pan_troglodytes": "NC_001643.1",
    "Gorilla_gorilla": "NC_011120.1",
    "Pongo_abelii": "NC_002083.1",
    "Hylobates_lar": "NC_002082.1",
    "Macaca_mulatta": "NC_005943.1",
    "Papio_anubis": "NC_020006.2",
    "Cercopithecus_mitis": "NC_023961.1",
    "Chlorocebus_sabaeus": "NC_008066.1",
    "Callithrix_jacchus": "NC_025586.1",
    "Saimiri_sciureus": "NC_012775.1",
}
EXPECTED_SHA256 = "73eb9e9a184b4f224859073de494329f6da6274cde30275be2420792319eb279"

# Vertebrate mitochondrial code (NCBI table 2): the standard code with
# TGA = W, ATA = M, and AGA/AGG = stop.
_BASES = "TCAG"
_STANDARD = "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG"
CODE = {a + b + c: _STANDARD[16 * i + 4 * j + k] for i, a in enumerate(_BASES) for j, b in enumerate(_BASES) for k, c in enumerate(_BASES)}
CODE.update({"TGA": "W", "ATA": "M", "AGA": "*", "AGG": "*"})


def translate(seq: str) -> str:
    return "".join(CODE[seq[i : i + 3]] for i in range(0, len(seq), 3))


def _identity(a: str, b: str) -> int:
    return sum(x == y for x, y in zip(a, b))


EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id={}&rettype=fasta_cds_na&retmode=text"


def cytb(accession: str) -> tuple[str, str]:
    """(location, CDS) of the single CYTB feature of ``accession``."""
    with urllib.request.urlopen(EFETCH.format(accession), timeout=60) as r:
        records = r.read().decode().split(">")[1:]
    hits = [rec for rec in records if re.search(r"\[gene=(CYTB|CYB|COB)\]", rec, re.I)]
    if len(hits) != 1:
        raise SystemExit(f"{accession}: {len(hits)} CYTB features")
    header, *lines = hits[0].split("\n")
    location = re.search(r"\[location=([^\]]+)\]", header).group(1)
    return location, "".join(lines)


def main() -> None:
    out = []
    ends = set()
    reference = ""
    for species, accession in ACCESSIONS.items():
        location, cds = cytb(accession)
        time.sleep(0.4)  # NCBI asks for at most 3 requests per second without a key
        if not (set(cds) <= set("ACGT") and len(cds) in (1140, 1141) and cds.startswith("ATG")):
            raise SystemExit(f"{species}: unexpected CDS ({len(cds)} nt)")
        seq = cds[: 3 * CODONS]
        # Colinearity checks on the translation: no internal stop codon, the
        # conserved W at codon 379, and the last 40 residues in register with
        # the first species' (an internal one-codon indel would shift them:
        # identity in register must be >= 20 and more than twice either
        # one-codon shift; observed 23-40 against at most 6).
        protein = translate(seq)
        reference = reference or protein
        tail = protein[-40:]
        in_register = _identity(tail, reference[-40:])
        shifted = max(_identity(tail, reference[-41:-1]), _identity(tail[1:], reference[-40:]))
        ends.add("*" not in protein and protein[-1] == "W" and in_register >= 20 and in_register > 2 * shifted)
        out.append(f">{species} {accession} CYTB {location} codons 1-{CODONS}\n")
        out.extend(seq[i : i + 60] + "\n" for i in range(0, len(seq), 60))
    if ends != {True}:
        raise SystemExit("the CDS ends do not line up; the ungapped alignment would be wrong")
    text = "".join(out)
    digest = hashlib.sha256(text.encode()).hexdigest()
    if EXPECTED_SHA256 and digest != EXPECTED_SHA256:
        raise SystemExit(f"fetched data changed: sha256 {digest}, expected {EXPECTED_SHA256}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(REPO)} (sha256 {digest})")


if __name__ == "__main__":
    sys.exit(main())
