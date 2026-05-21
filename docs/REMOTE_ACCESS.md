# Remote access (host from your PC)

Use this when you want to open the **demo UI** from another device (phone, laptop, office) or over the **internet**.

## Quick start (LAN — same Wi‑Fi)

1. Ensure Postgres and Redis are running locally (they stay on `localhost` — only the API/UI are exposed).

```bash
brew services start postgresql@14 redis
```

2. Enable remote mode in `.env` (or export for the session):

```bash
# Add to .env (recommended)
API_HOST=0.0.0.0
CORS_ALLOW_ALL=true
```

3. Start services in **three terminals**:

```bash
REMOTE_ACCESS=1 ./scripts/start-api.sh
./scripts/start-worker.sh
REMOTE_ACCESS=1 ./scripts/start-demo-ui.sh
```

Or print instructions + optional one-shot background start:

```bash
./scripts/start-remote.sh              # instructions
START_ALL=1 ./scripts/start-remote.sh  # API + worker + UI in background
```

4. On another device on the same network, open the **Demo UI** URL printed by the scripts, e.g. `http://192.168.1.42:5173`.

The UI talks to the API through Vite’s `/api` proxy on your Mac, so you only need port **5173** reachable on the LAN.

## Internet access (anywhere)

### Option A — Cloudflare Tunnel (easiest, no router config)

1. Install: `brew install cloudflared`
2. Start API, worker, and demo UI (remote mode above).
3. In a fourth terminal:

```bash
./scripts/tunnel-cloudflared.sh
```

4. Share the `https://….trycloudflare.com` URL cloudflared prints. That link reaches your local demo UI.

### Option B — Router port forwarding

Forward **TCP 5173** on your router to this Mac’s LAN IP. Use your public IP or DDNS hostname. Prefer HTTPS via a reverse proxy if exposing long-term.

## macOS firewall

If another device cannot connect, allow incoming connections for **Python** (API) and **node** (Vite) in **System Settings → Network → Firewall**, or temporarily disable the firewall for testing.

## Troubleshooting (phone can’t connect)

| Symptom | Fix |
|---------|-----|
| Page won’t load | Demo UI must be running: `./scripts/start-demo-ui.sh` — look for **Network: http://192.168.x.x:5173/** in the terminal |
| Wrong IP | Use the Mac’s LAN IP (`192.168.0.8` in this example), not `localhost` |
| UI only on laptop | Old Vite was bound to localhost; restart with `./scripts/start-demo-ui.sh` after pulling latest scripts |
| API 8000 unreachable from phone | OK for default setup — UI proxies `/api` on the Mac. Only restart API with `./scripts/start-api.sh` if you need direct API access |
| Guest Wi‑Fi | Some routers block phone ↔ laptop (“AP isolation”) — use the main Wi‑Fi or a tunnel |

Check listeners:

```bash
lsof -nP -iTCP:5173 -sTCP:LISTEN   # should show *:5173
curl -I http://$(ipconfig getifaddr en0):5173/
```

## Security

| Risk | Mitigation |
|------|------------|
| Default `API_KEY` | Set a strong `API_KEY` in `.env` before exposing |
| Public internet | Use Cloudflare Tunnel or VPN; avoid raw port-forward without auth |
| Postgres/Redis | Stay on `127.0.0.1` — do not bind them to `0.0.0.0` |

`CORS_ALLOW_ALL=true` is intended for **demo hosting only**, not production.

## Environment reference

| Variable | Default | Remote |
|----------|---------|--------|
| `REMOTE_ACCESS` | — | `1` enables `0.0.0.0` bind + permissive CORS |
| `API_HOST` / `BIND_HOST` | `127.0.0.1` | `0.0.0.0` |
| `API_PORT` | `8000` | same |
| `CORS_ALLOW_ALL` | `false` | `true` for LAN/mobile browsers hitting API directly |
| `CORS_ORIGINS` | — | Comma list instead of `*` if you need credentials |

## Direct API from a remote browser

If you set `VITE_API_URL=http://<lan-ip>:8000` in `apps/demo-ui/.env`, the browser calls the API directly — require `API_HOST=0.0.0.0` and `CORS_ALLOW_ALL=true` (or list your UI origin in `CORS_ORIGINS`).

Default setup uses the Vite proxy (`/api` → `127.0.0.1:8000`) and only requires opening port **5173**.

## Production-style preview (optional)

Build once, serve without Vite dev HMR:

```bash
cd apps/demo-ui && npm run build
REMOTE_ACCESS=1 npm run preview:remote
```

Still run API + worker with `REMOTE_ACCESS=1`.
