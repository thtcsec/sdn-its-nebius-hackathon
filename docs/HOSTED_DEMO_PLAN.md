# Hosted judge demo plan (cost-limited, safe)

**Status:** Config + server guards implemented. Do not deploy paid infra or flip repo visibility without owner approval.

See also: [HOSTED_SECURITY.md](./HOSTED_SECURITY.md).

## Goal

A judge opens a URL, lands on **JunctionTrace** (`/`), selects a scenario, runs **Investigate** (offline or Real Nebius), and sees:

1. Tool calls in the investigation timeline  
2. Retrieved evidence (telemetry + synthetic camera metadata)  
3. Nemotron conclude **or** clearly labeled deterministic / blocked path  
4. Safety-gate outcome  
5. OpenFlow = **mock** (never a real switch)

Research console remains at `/research`.

## Recommended stack

| Layer | Choice | Notes |
|-------|--------|-------|
| App | Flask `api.app` → JunctionTrace `/` | Same process as local `:8080` |
| Host | Railway / Render / Fly.io / Nebius VM | Owner approval before paid spend |
| Secrets | `NEBIUS_API_KEY`, `SDN_API_TOKEN`, budget envs | Never commit `.env` |
| OF | mock (default) | No Mininet / OVS |
| Camera | synthetic metadata fixtures | No RTSP |

## Cost & abuse controls (implemented)

1. **Server demo policy:** when `SDN_API_TOKEN` or `SDN_HOSTED_DEMO=1`, force `demo_mode=true` and `allow_containment_in_demo=false` (client cannot override).  
2. **Auth:** token required on `POST .../multistep`, `.../run`, `.../investigate`, and `GET .../audit`.  
3. **Rate / concurrency:** `JT_RATE_LIMIT_PER_MIN` (default 8), `JT_MAX_CONCURRENT_REAL` (default 2).  
4. **Daily budget:** `NEBIUS_DAILY_BUDGET_USD` (default 1.0) — 429 before model call.  
5. **Timeouts:** Nebius client ~60s; API maps `TimeoutError` → fail-closed `observe` (502).  
6. **Model:** `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`.

## Deploy steps (when approved)

```bash
pip install "python-dotenv>=1.0" "requests>=2.31" "pyyaml>=6" "Flask>=2.3" gunicorn
export PYTHONPATH=src:.
export NEBIUS_API_KEY=...
export NEBIUS_MODEL=nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B
export SDN_API_TOKEN=...          # required for hosted
export SDN_HOSTED_DEMO=1
export NEBIUS_DAILY_BUDGET_USD=1.0
export SDN_BIND_HOST=0.0.0.0
gunicorn -b 0.0.0.0:8080 "api.app:create_app()"
```

Health: `GET /api/v1/status`  
Product: `GET /` · Capabilities: `GET /api/v1/hackathon/capabilities`

## Judge script (≤3 min) — JunctionTrace

1. Open hosted URL → brand + problem + CTA + scenarios visible  
2. Scenario A (legitimate congestion) → Safe offline → show avoid-unnecessary-containment  
3. Scenario B (quiet zone / uncertain) → Real Nebius → show full trace; do **not** overclaim “credible attack”  
4. Show `LIVE Nebius / real_api` or honest blocked/budget error  
5. Open `/research` briefly to prove lab console preserved  
6. State limits: synthetic camera, mock OF, advisory latency, daily budget

## Explicit non-actions

- Do **not** deploy, flip visibility, upload YouTube, or submit Devpost without owner approval.
