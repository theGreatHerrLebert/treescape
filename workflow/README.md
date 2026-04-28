# Workflow

Two-tier validation infrastructure for treescape's EVIDENT manifest.

## Tiers

- `ci` — light, runs on every PR. `python` + `maturin` + `ete3` + `biopython` + `numpy`/`pandas`.
- `release` — heavy, runs before any release tag. Adds R + Bioconductor + ggtree for the third independent layout oracle.

## Files

- `validate_manifest.py` — structural validator for `evident.yaml`. Adapted from `evident/workflow/validate_manifest.py`; same schema.
- `Dockerfile.evident-base` — `ci`-tier image. (Phase 0 ships only the structural validator; the layered images land alongside Phase 2.)
- `Dockerfile.evident-release` — `release`-tier image with R/Bioconductor.
- `scripts/oracle_ggtree.R` — invoked by claim #5 runner.

## Usage

```bash
# Validate manifest structure (no oracles run)
python workflow/validate_manifest.py evident.yaml

# Run all ci-tier oracle claims
pytest tests/oracle -v -m "not release_only"

# Run release-tier (requires R + Bioconductor; must pass before tag)
pytest tests/oracle -v
```
