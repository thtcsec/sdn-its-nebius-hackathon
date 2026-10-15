# Hosted judge demo plan (cost-limited, safe)

**Status:** Plan only — do not deploy paid infra or flip repo visibility without owner approval.

## Goal

A judge opens a URL, selects a fixture/scenario, runs **Investigate** and optionally **Run real Nebius**, and sees:

1. Tool calls in the storyboard  
2. Retrieved evidence (telemetry + synthetic camera metadata)  
3. Nemotron conclude **or** clearly labeled `deterministic_fallback`  
4. Safety-gate outcome  
5. OpenFlow = **mock** (never a real switch)

## Recommended stack (cheap / free tier first)

| Layer | Choice | Notes |
|-------|--------|-------|
| App | Existing Flask `api.app` | Same console as local `:8080` |
| Host | Railway / Render / Fly.io free or Nebius VM | Keep region near Token Factory if latency matters |
| Secrets | Platform env: `NEBIUS_API_KEY`, `NEBIUS_MODEL`, `NEBIUS_BASE_URL` | Never commit `.env` |
| OF | mock (default) | No Mininet / OVS required |
| Camera | synthetic metadata fixtures | No RTSP |

## Cost controls (mandatory)

1. **Demo mode default:** `demo_mode=true`; containment blocked unless explicitly allowed.  
2. **Rate limit:** e.g. 5 live Nebius investigations / IP / hour; offline unlimited.  
3. **Hard budget:** stop live calls when estimated spend ≥ $1–2/day (env `NEBIUS_DAILY_BUDGET_USD`).  
4. **Model:** keep `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` (cheap Nano).  
5. **Timeouts:** 60–90s request timeout; show error in UI, never hang.  
6. **Auth (optional):** simple shared judge token query/header to reduce abuse.

## Deploy steps (when approved)

```bash
# build
pip install "python-dotenv>=1.0" "requests>=2.31" "pyyaml>=6" "Flask>=2.3" gunicorn
export PYTHONPATH=src:.
export NEBIUS_API_KEY=...
export NEBIUS_MODEL=nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B
export SDN_BIND_HOST=0.0.0.0
gunicorn -b 0.0.0.0:8080 "api.app:create_app()"
```

Health: `GET /api/v1/status`  
Hackathon: `GET /api/v1/hackathon/incidents`, `POST /api/v1/hackathon/multistep`.

## Judge script (≤3 min video later)

1. Open hosted URL → scroll to **Hackathon · Incident agent**  
2. Select `scenario_rush_vs_attack` → **Run offline** (show deterministic labels)  
3. Select `scenario_missing_camera` → **Run real Nebius** → show tools + `nemotron_conclude` + observe  
4. Show audit JSON + `OF: mock` pill  
5. State limitations: synthetic camera, mock OF, advisory latency ~15–20s

## Remaining release blockers (unchanged by this plan)

- Public repo + MIT visible on GitHub About  
- Public YouTube &lt;3 min (actual recording, not script only)  
- Hosted URL live  
- Owner approval before visibility flip / Devpost submit
