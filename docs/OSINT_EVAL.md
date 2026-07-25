# OSINT evaluation

## Purpose

Measure how often the hybrid OSINT / `ProfileAnalyzer` stack correctly flags risk signals on a **synthetic fixture golden set**.

**Disclaimer:** These metrics are **not** production portfolio accuracy. They guard regressions on known demo fraud patterns (employer mismatch, sanctions, virtual office, inactive entity).

## How to run

```bash
# Fixture mode (default for eval)
OSINT_MODE=fixture python scripts/eval_osint.py

# Writes: output/osint_eval_latest.json
# CI: pytest tests/test_osint_eval.py
```

Golden cases: [`data/evals/osint_golden.json`](../data/evals/osint_golden.json).

## Baseline (fixture corpus)

Recorded from `scripts/eval_osint.py` on the golden set shipped with this repo:

| Metric | Precision | Recall | F1 | Support |
|--------|-----------|--------|-----|---------|
| `has_employer_mismatch` | 1.000 | 1.000 | 1.000 | 2 |
| `has_sanctions_hit` | 1.000 | 1.000 | 1.000 | 1 |
| `address_high_risk` | 1.000 | 1.000 | 1.000 | 2 |
| `any_flagged_or_mismatch` | 1.000 | 1.000 | 1.000 | 4 |

- **Case pass rate:** 8/8 (100%)
- **CI floors:** case pass rate ≥ 0.85; each F1 above ≥ 0.99

## What “pass” means per case

Each golden case asserts a subset of:

- business/employer status membership
- employer mismatch / sanctions hit / address high-risk / adverse media / any flagged|mismatch

## Expanding toward real accuracy claims

1. Add anonymized lender-labeled cases (with legal approval)
2. Separate live-provider eval (network + keys) from fixture CI
3. Track underwriter agreement rate on pilot cases ([MRM_COMPLIANCE.md](MRM_COMPLIANCE.md))
