"""Keeps the structured fields of ``evident.yaml`` honest.

The upstream gates (``evident/workflow/validate_manifest.py``,
``typed-trust``) check the schema; they cannot check that the data is
true. This runner does, for what can be checked mechanically:

- the ``treescape`` pin equals the workspace version in ``Cargo.toml``;
- every Python oracle pin equals the installed version (so an unpinned
  environment fails instead of silently producing evidence against a
  different oracle);
- every ``corpus_sha`` equals the hash recomputed from
  ``tests/fixtures/corpora.toml``, and every named corpus exists;
- the ggtree pin equals what the release image has (release tier only).

Conventions: ``docs/conventions.md``, "EVIDENT manifest".
"""

from __future__ import annotations

import importlib.metadata
import shutil
import subprocess
import sys
import tomllib

import pytest
import yaml

from _julia import REPO

sys.path.insert(0, str(REPO / "scripts"))
from corpus_sha import corpora, corpus_sha  # noqa: E402

MANIFEST = yaml.safe_load((REPO / "evident.yaml").read_text())
CLAIMS = MANIFEST["claims"]
CORPORA = corpora()
# Oracle name in the manifest -> Python distribution that provides it.
PYTHON_ORACLES = {"Biopython": "biopython", "ete3": "ete3", "hypothesis": "hypothesis", "scikit-bio": "scikit-bio", "SciPy": "scipy"}
# In-repository oracles, pinned to the workspace version.
IN_REPO_ORACLES = {"treescape-reference", "golden-snapshots", "self-consistency", "treescape-python", "generating-tree"}
# Oracles whose pin is checked elsewhere: the R packages in the release
# image (below); the Julia harness by the CI matrix that runs it.
OTHER_ORACLES = {"ggtree", "ape", "phangorn", "julia-subprocess"}


def _pins(oracle: str) -> set[str]:
    return {c["pinned_versions"][oracle] for c in CLAIMS if oracle in c.get("pinned_versions", {})}


def test_upstream_validator_accepts_manifest() -> None:
    proc = subprocess.run(
        [sys.executable, str(REPO / "evident/workflow/validate_manifest.py"), "--strict-release-pins", str(REPO / "evident.yaml")],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_treescape_pin_is_the_workspace_version() -> None:
    version = tomllib.loads((REPO / "Cargo.toml").read_text())["workspace"]["package"]["version"]
    assert _pins("treescape") == {version}


def test_in_repository_oracles_pin_the_workspace_version() -> None:
    version = tomllib.loads((REPO / "Cargo.toml").read_text())["workspace"]["package"]["version"]
    for oracle in IN_REPO_ORACLES:
        assert _pins(oracle) <= {version}, oracle


def test_every_oracle_has_a_pin_check() -> None:
    """A new oracle must be classified here, or its pin is never checked."""
    vocabulary = set(MANIFEST["vocabularies"]["oracle"])
    known = set(PYTHON_ORACLES) | IN_REPO_ORACLES | OTHER_ORACLES
    assert vocabulary == known, f"unclassified: {sorted(vocabulary - known)}; stale: {sorted(known - vocabulary)}"


@pytest.mark.parametrize("oracle", sorted(PYTHON_ORACLES))
def test_python_oracle_pins_match_installed(oracle: str) -> None:
    pins = _pins(oracle)
    assert len(pins) == 1, f"{oracle} pinned inconsistently across claims: {pins}"
    try:
        installed = importlib.metadata.version(PYTHON_ORACLES[oracle])
    except importlib.metadata.PackageNotFoundError:
        pytest.fail(f"{oracle} is named as an oracle but not installed")
    assert pins == {installed}, f"{oracle}: manifest pins {pins.pop()}, installed {installed}"


@pytest.mark.parametrize("claim", [c for c in CLAIMS if "corpus_sha" in c.get("inputs", {})], ids=lambda c: c["id"])
def test_corpus_sha_matches_files(claim: dict) -> None:
    name = claim["inputs"]["corpus"]
    assert name in CORPORA, f"{claim['id']}: corpus {name!r} not in tests/fixtures/corpora.toml"
    assert claim["inputs"]["corpus_sha"] == corpus_sha(CORPORA[name]), (
        f"{claim['id']}: corpus {name!r} changed; update inputs.corpus_sha "
        f"(python scripts/corpus_sha.py {name})"
    )


def test_fixture_corpora_are_named_and_hashed() -> None:
    """A claim over fixture files names a corpus from corpora.toml and pins its hash."""
    for claim in CLAIMS:
        inputs = claim.get("inputs", {})
        classes = set(inputs.get("classes", [])) | ({inputs["class"]} if "class" in inputs else set())
        if "fixture" in classes or inputs.get("corpus") in CORPORA:
            assert inputs.get("corpus") in CORPORA, f"{claim['id']}: fixture corpus {inputs.get('corpus')!r} not in corpora.toml"
            assert "corpus_sha" in inputs, f"{claim['id']}: corpus {inputs['corpus']!r} has no corpus_sha"


@pytest.mark.release_only
def test_ggtree_pin_matches_release_image() -> None:
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.fail("Rscript not found; the release tier runs inside workflow/Dockerfile.evident-release")
    expr = (
        'cat(sprintf("%s (Bioconductor %s, R %s)", packageVersion("ggtree"), '
        'BiocManager::version(), paste(R.version$major, R.version$minor, sep=".")))'
    )
    actual = subprocess.run([rscript, "-e", expr], capture_output=True, text=True, check=True).stdout.strip()
    assert _pins("ggtree") == {actual}


@pytest.mark.release_only
@pytest.mark.parametrize("package", ["ape", "phangorn"])
def test_r_package_pins_match_release_image(package: str) -> None:
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.fail("Rscript not found; the release tier runs inside workflow/Dockerfile.evident-release")
    expr = f'cat(as.character(packageVersion("{package}")))'
    actual = subprocess.run([rscript, "-e", expr], capture_output=True, text=True, check=True).stdout.strip()
    assert _pins(package) == {actual}


def test_random_corpus_matches_its_generator() -> None:
    """The checked-in random trees are exactly what scripts/gen_random_trees.py writes."""
    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "gen_random_trees.py"), "--check"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_tree_corpus_counts_match_n() -> None:
    """For a claim over a corpus of tree files only, inputs.n is the number of trees."""
    for claim in CLAIMS:
        inputs = claim.get("inputs", {})
        files = CORPORA.get(inputs.get("corpus"), [])
        if files and inputs.get("class") == "fixture" and all(f.endswith(".nwk") for f in files):
            assert inputs.get("n") == len(files), f"{claim['id']}: n={inputs.get('n')} but corpus has {len(files)} trees"
