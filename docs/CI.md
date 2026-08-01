# CI & branch protection

## Required checks (PRs into `main` / `master`)

Workflow: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)

| Check | Job | What it runs |
|-------|-----|----------------|
| **security** | `security` | Gitleaks, `pip-audit`, `npm audit --omit=dev`, Trivy fs (HIGH/CRITICAL) |
| **backend** | `backend` | `pip install -e ".[dev]"`, ruff, unit + integration/e2e (Postgres service) |
| **frontend** | `frontend` | `npm ci`, production build, Vitest, Playwright smoke |
| **ci-success** | gate | Fails unless security + backend + frontend all succeed |

Branch protection / ruleset requires **`ci-success`** (and **security** / **backend** / **frontend**) before merge.

Configured on this repo:
- Ruleset: [Protect main](https://github.com/alsy99/underwrite-agent/rules/20180979) (`main` + `master`)
- Classic branch protection on `main`: required checks + no force-push + enforce admins

## Local parity

```bash
./scripts/setup_test_db.sh
./scripts/run_tests.sh backend
cd apps/demo-ui && npm ci && npm run build && npm test
```
