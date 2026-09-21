# Workflow

Two-tier validation infrastructure for treescape's EVIDENT manifest.

## Tiers

- `ci` — light, runs on every push to `main` and every PR. `python` + `maturin` + the pinned oracles in `tests/requirements-oracles.txt` (ete3, Biopython, hypothesis) + `polars` (+ Julia in the `julia` job).
- `release` — heavy, adds R + Bioconductor (pinned to 3.22) + ggtree for the third independent layout oracle. Runs when a `v*` tag is pushed and on a manual run of the `ci` workflow; run it manually on `main` (or locally in the image) and see it pass **before** pushing a release tag.

## Files

- `Dockerfile.evident-release` — `release`-tier image with R/Bioconductor and the same pinned Python oracles as CI.
- `scripts/oracle_ggtree.R` — invoked by the ggtree claim runners.

The manifest is validated by the upstream EVIDENT tools in the `evident/` submodule (`evident/workflow/validate_manifest.py`, `evident/typed-trust`); treescape keeps no copy of the schema. Oracle pins, corpus hashes and the project version in `evident.yaml` are checked by `tests/oracle/test_manifest.py`.

## Usage

```bash
# Validate the manifest (schema + typed-trust translation; no oracles run)
python evident/workflow/validate_manifest.py --strict-release-pins evident.yaml
cargo build --release --manifest-path evident/typed-trust/Cargo.toml
evident/typed-trust/target/release/typed-trust evident.yaml > /dev/null

# Run ci-tier oracle claims (excludes release_only-marked tests)
pytest tests/oracle -v -m "not release_only"

# Run release-tier (requires R + Bioconductor; must pass before tag)
pytest tests/oracle -v -m release_only
```

The `release_only` mark is registered in the workspace `pyproject.toml`. It is carried by the two ggtree layout runners and by the ggtree pin check in `tests/oracle/test_manifest.py`.
