# Workflow

Two-tier validation infrastructure for treescape's EVIDENT manifest.

## Tiers

- `ci` — light, runs on every push to `main` and every PR. `python` + `maturin` + `ete3` + `biopython` + `polars` (+ Julia in the `julia` job).
- `release` — heavy, adds R + Bioconductor + ggtree for the third independent layout oracle. Runs when a `v*` tag is pushed and on a manual run of the `ci` workflow; run it manually on `main` and see it pass **before** pushing a release tag.

## Files

- `validate_manifest.py` — structural validator for `evident.yaml`. Adapted from `evident/workflow/validate_manifest.py`; same schema.
- `Dockerfile.evident-base` — lightweight manifest validator (`docker build -f workflow/Dockerfile.evident-base .` from the repo root).
- `Dockerfile.evident-release` — `release`-tier image with R/Bioconductor.
- `scripts/oracle_ggtree.R` — invoked by claim #5 runner.

## Usage

```bash
# Validate manifest structure (no oracles run)
python workflow/validate_manifest.py evident.yaml

# Run ci-tier oracle claims (excludes release_only-marked tests)
pytest tests/oracle -v -m "not release_only"

# Run release-tier (requires R + Bioconductor; must pass before tag)
pytest tests/oracle -v -m release_only
```

The `release_only` mark is registered in the workspace `pyproject.toml`. Currently only `tests/oracle/test_layout_vs_ggtree.py` carries it; future heavy oracles will add the same mark.
