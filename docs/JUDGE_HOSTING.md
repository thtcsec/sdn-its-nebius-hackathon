# Judge hosting package (production-like, single-worker)

**Do not provision or charge cloud without owner approval.**  
Target availability: through **2026-12-15** (official judging window).  
**Next milestone:** a working public `https://$JT_DOMAIN/` URL. Video work is frozen.

Local Docker smoke this session: `python scripts/smoke_judge_docker.py` → **7/7** (`artifacts/hackathon/docker_smoke_report.json`, 2026-10-20T14:03Z). Loopback only — **not** a public URL.

OpenFlow stays **mock**. This package never attaches to a real traffic switch. Recommendations are advisory.

Application `NEBIUS_DAILY_BUDGET_USD` is **not** a Nebius provider hard cap. Set a Token Factory budget alert and be ready to revoke the key.

## Package layout

| Path | Purpose |
|------|---------|
| `docker/Dockerfile.judge` | Light Flask/Gunicorn image (no torch) |
| `deploy/judge/docker-compose.yml` | `app` (1 worker) + `caddy` (HTTPS) |
| `deploy/judge/Caddyfile` | TLS + trusted `X-Forwarded-For` |
| `deploy/judge/.env.example` | Secret template |

## Deploy commands (when approved)

```bash
# 1) Secrets
cp deploy/judge/.env.example deploy/judge/.env
# Edit: SDN_API_TOKEN (≥16 strong), NEBIUS_API_KEY, JT_DOMAIN=your.hostname

# 2) DNS: A/AAAA record for JT_DOMAIN → host public IP; ports 80/443 open

# 3) Build & start
cd deploy/judge
docker compose up -d --build

# 4) Verify
curl -fsS https://$JT_DOMAIN/api/v1/status
curl -fsS https://$JT_DOMAIN/api/v1/hackathon/capabilities
# Expect api_token_required=true, of_backend_default=mock, hosted_demo_enforced=true
```

Judge UI: `https://<JT_DOMAIN>/` — paste `SDN_API_TOKEN` in the session token field.

**External checks (from a network that is not the VM):**

```bash
curl -fsSI https://$JT_DOMAIN/ | head
curl -fsS https://$JT_DOMAIN/ | grep -F "JunctionTrace"
curl -fsS https://$JT_DOMAIN/api/v1/hackathon/capabilities
# of_backend_default must be mock; api_token_required must be true
curl -sS -o /dev/null -w "%{http_code}\n" -X POST https://$JT_DOMAIN/api/v1/hackathon/multistep \
  -H "Content-Type: application/json" \
  -d '{"scenario_id":"scenario_rush_vs_attack","mode":"real"}'
# expect 401 without X-API-Token
```

In a real browser (phone or second laptop): open `/`, paste the judge token, run Scenario A offline then Scenario B Real Nebius. Confirm **OpenFlow: mock** remains on the chip. The demo does not install flows on a physical switch.

## Rollback

```bash
cd deploy/judge
docker compose down
# Restore previous image/code:
git checkout <previous-good-sha>
docker compose up -d --build
# Quota volume `jt_quota` is retained across redeploys unless you run:
# docker volume rm judge_jt_quota   # destructive — loses daily quota state
```

## Estimated operating cost (through 2026-12-15)

| Item | Estimate |
|------|----------|
| Small VM / PaaS (1 vCPU, 512MB–1GB) | ~$5–12 / month → **~$10–25** for ~2 months |
| TLS (Caddy Let’s Encrypt) | $0 |
| Nebius Token Factory (app budget $1/day, rate-limited) | **≤ $1/day** application cap; expect far less if judges are few (typical demo day ≪ $1) |
| Bandwidth | Negligible for demo traffic |

**Total ballpark:** **$15–40** host + **&lt;$30** Nebius if busy; often **&lt;$20** all-in for a quiet judge period.  
Not a Nebius account hard cap — rotate/revoke `NEBIUS_API_KEY` if spend spikes.

## DNS, firewall, secrets

| Item | Requirement |
|------|-------------|
| DNS | `A` and/or `AAAA` for `JT_DOMAIN` → VM public IP. Wait for propagation before expecting Let’s Encrypt. |
| Ports | **80** (HTTP-01) and **443** (HTTPS). Do not publish app port 8080. |
| `SDN_API_TOKEN` | ≥16 chars, not a placeholder; `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `NEBIUS_API_KEY` | Server-side only in `deploy/judge/.env` (gitignored). Never in the image, browser, or Devpost text. |
| Workers | **1** Gunicorn worker. SQLite quota is not multi-worker safe. |

## Spending limits and kill-switch

| Control | What it actually is |
|---------|---------------------|
| `NEBIUS_DAILY_BUDGET_USD=1.0` | Application estimate; fail-closed in-process. **Not** a Nebius hard cap. |
| `JT_RATE_LIMIT_PER_MIN=8` | Per-IP real-mode rate limit (trusted `X-Forwarded-For` only behind Caddy). |
| `JT_MAX_CONCURRENT_REAL=2` | In-flight real investigations. |
| `JT_RESERVE_USD_PER_REAL=0.05` | Reserved before a live call; crash orphans stay charged. |
| Provider | Token Factory dashboard budget alert + **revoke/rotate key** if spend spikes. Optionally pause the VM. |

**Max exposure if app quota is bypassed:** unbounded at the provider until you revoke the key. Treat key revoke as the real kill-switch.

## Restart, logs, backup, teardown

```bash
cd deploy/judge
docker compose ps
docker compose logs -f --tail=200 app
docker compose restart app          # quota volume persists
docker compose exec app ls -l /data/quota
# backup quota
docker run --rm -v judge_jt_quota:/data -v "$PWD:/backup" alpine tar czf /backup/jt_quota.tgz /data
# teardown (stops public demo)
docker compose down
# destroy quota (loses daily spend state)
# docker compose down -v
```

Keep the stack up through **2026-12-15**: `restart: unless-stopped`, weekly health curl, do not `down -v` unless abandoning the demo.

## Judge-friendly access

1. Devpost **Try it out** URL: `https://<JT_DOMAIN>/` (never `localhost`).
2. Testing instructions: paste the judge `SDN_API_TOKEN` into the on-page token field (not stored in localStorage).
3. If the host must stay IP-restricted, put the same URL + token in Devpost **testing instructions** (rules allow credentials for private sites).
4. Point judges at Scenario A (offline congestion) then Scenario B (Real Nebius). Expect **10–30 s** on live Nemotron.
5. State in testing instructions: *OpenFlow is mock; the demo does not control a real traffic switch. Camera metadata is synthetic.*

## Safety properties

- `SDN_HOSTED_DEMO=1` → refuse start without strong token + mock OF
- Legacy `/api/v1/hackathon/run` + `/investigate` → **410**
- SQLite quota on named volume; crash orphans charged (not refunded)
- `JT_TRUSTED_PROXY=1` behind Caddy only
- Logs: access lines only; no Authorization bodies
- Image copies `src`, `api`, `dashboard`, `configs`, `datasets/hackathon`, `scripts` — not `.env` (see `.dockerignore`)
