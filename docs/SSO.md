# SSO / OIDC

## Modes (`AUTH_MODE`)

| Value | Behavior |
|-------|----------|
| `api_key` | Shared `API_KEY` + tenant `api_keys` table only |
| `oidc` | Bearer JWT only (HS256 via `OIDC_DEV_SECRET` or RS256 via JWKS) |
| `both` (default) | Try API key, then tenant key, then JWT |

## OIDC claims

| Claim (configurable) | Env | Purpose |
|----------------------|-----|---------|
| `tenant_id` | `OIDC_TENANT_CLAIM` | Soft tenancy; overrides client `tenant_id` |
| `roles` | `OIDC_ROLES_CLAIM` | `admin` / `underwriter` / `reviewer` |
| `sub`, `email` | — | Actor identity for audit |

## Roles

| Role | Capabilities |
|------|----------------|
| `admin` | All + webhook admin |
| `underwriter` | Create cases, upload spreads, generate memos |
| `reviewer` | Read cases / audit / export |

## Local JWT (CI / demo)

```bash
# HS256 with OIDC_DEV_SECRET
python - <<'PY'
import jwt
print(jwt.encode(
  {"sub":"u1","email":"uw@test","tenant_id":"default","roles":["underwriter"]},
  "dev-oidc-hs256-change-me", algorithm="HS256"))
PY
```

Authorization: `Bearer <token>`

## Production

1. Set `AUTH_MODE=oidc` (or `both` during migration)
2. Set `OIDC_ISSUER`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL` (or rely on `{issuer}/.well-known/jwks.json`)
3. Clear or rotate `OIDC_DEV_SECRET` so HS256 is not an accidental backdoor (leave empty to disable)
4. Map IdP groups → `roles` claim

See also [ENTERPRISE.md](ENTERPRISE.md).
