"""Oracle runner for claim ``treescape-newick-roundtrip``.

Two oracles per the manifest:

  1. **self (round-trip)** — for every canonical fixture, parsing then
     writing then re-parsing produces a structurally identical tree.

  2. **Biopython.Phylo** — on small/medium fixtures, our parsed tree
     agrees with Biopython's parse on the tip-name set and on tip
     branch lengths (within 1e-9). Edge fixtures (NHX, negative
     branches) are excluded with the reason recorded below.

Phase 1 status: the Rust path is reachable only via `cargo test`; this
file exercises the Python reference, which the Rust impl is held to
match in Phase 4. Until then, this test gates the convention-owner.
"""

from __future__ import annotations

import json
import pathlib
import time

import pytest

from treescape_reference.newick import parse as ref_parse, write as ref_write

try:
    from Bio import Phylo
    from io import StringIO

    HAVE_BIOPYTHON = True
except ImportError:  # pragma: no cover - environment-dependent
    HAVE_BIOPYTHON = False


FIXTURES_DIR = pathlib.Path(__file__).parent.parent / "fixtures" / "trees"
REPORT_DIR = pathlib.Path(__file__).parent / "reports"

CANONICAL_FIXTURES = [
    FIXTURES_DIR / "small" / "two_tip.nwk",
    FIXTURES_DIR / "small" / "balanced_4.nwk",
    FIXTURES_DIR / "small" / "unbalanced_5.nwk",
    FIXTURES_DIR / "edge" / "quoted_names.nwk",
    FIXTURES_DIR / "edge" / "trifurcation_root.nwk",
    FIXTURES_DIR / "edge" / "neg_branches.nwk",
    FIXTURES_DIR / "edge" / "nhx_comments.nwk",
]

# Documented in evident.yaml claim #1's `assumptions`. These fixtures
# stay in the round-trip oracle but skip Biopython parity.
BIOPYTHON_EXCLUDED = {
    "neg_branches.nwk": "Biopython parses negative branch lengths but its "
                       "internal handling differs from ours; comparison is "
                       "documented as out of scope for v0.1.",
    "nhx_comments.nwk": "Biopython does not preserve NHX annotations; the "
                       "comparison would be circular since both parsers "
                       "drop them.",
}

BRANCH_LEN_TOL = 1e-9


# ----- Round-trip claim oracle ----------------------------------------------


@pytest.mark.parametrize("fixture", CANONICAL_FIXTURES, ids=lambda p: p.name)
def test_reference_roundtrip(fixture: pathlib.Path) -> None:
    """parse(write(parse(s))) is structurally identical to parse(s)."""
    src = fixture.read_text()
    t1 = ref_parse(src)
    serialized = ref_write(t1)
    t2 = ref_parse(serialized)
    assert t1.topology_hash() == t2.topology_hash(), (
        f"topology hash mismatch on {fixture.name}"
    )
    bl1 = [n.branch_length for n in t1.postorder()]
    bl2 = [n.branch_length for n in t2.postorder()]
    assert bl1 == bl2, f"branch lengths drifted on {fixture.name}"
    names1 = [n.name for n in t1.postorder()]
    names2 = [n.name for n in t2.postorder()]
    assert names1 == names2, f"names drifted on {fixture.name}"


# ----- Biopython parity oracle ----------------------------------------------


def _biopython_tip_branch_lengths(src: str) -> dict[str, float]:
    bio_tree = Phylo.read(StringIO(src), "newick")
    return {
        t.name: (t.branch_length if t.branch_length is not None else 0.0)
        for t in bio_tree.get_terminals()
    }


def _biopython_tip_names(src: str) -> set[str]:
    bio_tree = Phylo.read(StringIO(src), "newick")
    return {t.name for t in bio_tree.get_terminals()}


_BIO_FIXTURES = [
    f for f in CANONICAL_FIXTURES if f.name not in BIOPYTHON_EXCLUDED
]


@pytest.mark.skipif(not HAVE_BIOPYTHON, reason="Biopython not installed")
@pytest.mark.parametrize("fixture", _BIO_FIXTURES, ids=lambda p: p.name)
def test_biopython_tip_set_matches(fixture: pathlib.Path) -> None:
    """Tip name set is identical to Biopython's."""
    src = fixture.read_text()
    our = {n.name for n in ref_parse(src).postorder() if n.is_tip()}
    bio = _biopython_tip_names(src)
    assert our == bio, f"tip name set differs on {fixture.name}"


@pytest.mark.skipif(not HAVE_BIOPYTHON, reason="Biopython not installed")
@pytest.mark.parametrize("fixture", _BIO_FIXTURES, ids=lambda p: p.name)
def test_biopython_tip_branch_lengths_match(fixture: pathlib.Path) -> None:
    """Tip branch lengths agree with Biopython within 1e-9 absolute."""
    src = fixture.read_text()
    our_tree = ref_parse(src)
    our = {
        n.name: n.branch_length
        for n in our_tree.postorder()
        if n.is_tip()
    }
    bio = _biopython_tip_branch_lengths(src)
    assert set(our) == set(bio)
    for name in our:
        delta = abs(our[name] - bio[name])
        assert delta < BRANCH_LEN_TOL, (
            f"branch length for {name!r} on {fixture.name}: "
            f"ours={our[name]!r} biopython={bio[name]!r} delta={delta}"
        )


# ----- Artifact emission ----------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _emit_report() -> None:
    """Per evident.yaml claim #1: write a JSON artifact summarizing the run."""
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-newick-roundtrip",
        "version": "0.1",
        "timestamp_utc": int(time.time()),
        "fixtures_roundtripped": [f.name for f in CANONICAL_FIXTURES],
        "fixtures_biopython_compared": [f.name for f in _BIO_FIXTURES],
        "fixtures_biopython_excluded": BIOPYTHON_EXCLUDED,
        "branch_length_tolerance": BRANCH_LEN_TOL,
        "biopython_available": HAVE_BIOPYTHON,
    }
    (REPORT_DIR / "newick_roundtrip.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
