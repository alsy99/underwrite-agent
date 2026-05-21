# Internet deploy: GitHub Pages + ngrok backend

Host the **demo UI** on GitHub Pages (password-protected) and keep the **API + worker** on your Mac, exposed through **ngrok**.

```
[Browser] → GitHub Pages (static UI + login password)
              ↓ HTTPS + Bearer API_KEY
         ngrok tunnel → your Mac :8000 (FastAPI + ARQ worker)
```

## 1. Secrets on your Mac (`.env`)

```bash
# Strong API key (must match GitHub secret VITE_API_KEY)
API_KEY=replace-with-long-random-string

# Allow GitHub Pages origin
CORS_GITHUB_PAGES=true

# Optional: UI password for local dev (use hash for production builds)
# VITE_UI_PASSWORD_HASH=$(./scripts/hash-ui-password.sh 'your-demo-password')
```

Restart API and worker after changing `API_KEY`.

## 2. Start backend + ngrok

Terminal 1 — API:

```bash
./scripts/start-api.sh
```

Terminal 2 — worker:

```bash
./scripts/start-worker.sh
```

Terminal 3 — ngrok (API only):

```bash
# Optional extra gate on the tunnel (user:password)
export NGROK_BASIC_AUTH='you:your-ngrok-password'
./scripts/tunnel-ngrok.sh
```

Copy the **https** forwarding URL (e.g. `https://abc123.ngrok-free.app`).  
Set GitHub repository secrets (Settings → Secrets and variables → Actions):

| Secret | Value |
|--------|--------|
| `VITE_API_URL` | `https://abc123.ngrok-free.app` (no trailing slash) |
| `VITE_API_KEY` | Same as `API_KEY` in `.env` |
| `UI_PASSWORD` | Demo login password for the web UI |

> Free ngrok URLs change when you restart ngrok — update `VITE_API_URL` and re-run the deploy workflow (or push to `main`).

Install ngrok: `brew install ngrok/ngrok/ngrok` and `ngrok config add-authtoken <token>`.

## 3. Enable GitHub Pages

1. Push this repo to GitHub.
2. **Settings → Pages → Build and deployment → Source:** **GitHub Actions**.
3. Push to `main` / `master` (or run workflow **Deploy demo UI to GitHub Pages** manually).

Your site URL:

`https://<github-username>.github.io/<repo-name>/`

Example: `https://adnanshahid.github.io/underwrite-agent/`

## 4. Password protection (two layers)

| Layer | What it does |
|-------|----------------|
| **UI login** | `UI_PASSWORD` → hashed at build time; required before the app loads |
| **API key** | Every API call sends `Authorization: Bearer <VITE_API_KEY>` |
| **ngrok basic auth** (optional) | `NGROK_BASIC_AUTH=user:pass` on the tunnel |

The UI password is embedded as a hash in the static build — sufficient for a private demo, not bank-grade security. Use a long `API_KEY` and rotate ngrok if the URL leaks.

## 5. Local UI with password

```bash
export VITE_UI_PASSWORD_HASH=$(./scripts/hash-ui-password.sh 'your-demo-password')
export VITE_API_KEY=your-api-key
./scripts/start-demo-ui.sh
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| UI loads, API errors | ngrok running? `VITE_API_URL` secret matches current ngrok URL? |
| CORS error | `CORS_GITHUB_PAGES=true` in `.env`, restart API |
| ngrok browser warning | Already handled via `ngrok-skip-browser-warning` header in the UI |
| 404 on refresh | Workflow copies `index.html` → `404.html` for SPA routing |
| Wrong assets path | `VITE_BASE_PATH` is set automatically to `/<repo-name>/` in CI |

## Alternative: LAN only

See [REMOTE_ACCESS.md](./REMOTE_ACCESS.md) for same-Wi‑Fi hosting without GitHub/ngrok.
