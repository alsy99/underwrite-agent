# Spreading

Upload CSV/XLSX financial spreads and compare to stated figures in case metadata.

## API

- `POST /v1/cases/{id}/spreads` — multipart file
- `GET /v1/cases/{id}/spreads` — latest payload + variances

## Canonical metrics

`gross_revenue`, `noi`, `avg_monthly_deposits`, `stated_income`, `ebitda`

## Thresholds (default)

| Vertical | Metric | Threshold |
|----------|--------|-----------|
| SBA 7(a) | gross_revenue | 10% |
| CRE | noi | 10% |
| Bank-statement | avg_monthly_deposits / stated_income | 15% |

## Fixtures

`data/fixtures/spreads/` — `sba_clean.csv`, `sba_mismatch.csv`, `bsm_mismatch.csv`

High variances emit LOS event `spread.variance_high` when webhooks configured.
