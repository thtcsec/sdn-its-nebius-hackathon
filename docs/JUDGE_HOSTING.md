# Judge hosting package (production-like, single-worker)

**Do not provision or charge cloud without owner approval.**  
Target availability: through **2026-12-15** (official judging window).

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

## Safety properties

- `SDN_HOSTED_DEMO=1` → refuse start without strong token + mock OF
- Legacy `/run` + `/investigate` → 410
- SQLite quota on named volume; crash orphans charged (not refunded)
- `JT_TRUSTED_PROXY=1` behind Caddy only
- Logs: access lines only; no Authorization bodies
