# JunctionTrace — safe single-instance hosting runbook

**Prerequisite:** owner approval before provisioning any paid host.  
**Topology:** one process, one worker (SQLite quota is not multi-worker safe).

## 1. Environment (required)

```bash
export SDN_HOSTED_DEMO=1
export SDN_API_TOKEN='<≥16 char strong random token>'
export SDN_OF_BACKEND=mock
export SDN_BIND_HOST=0.0.0.0
export NEBIUS_API_KEY='<server-only Token Factory key>'
export NEBIUS_MODEL=nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B
export NEBIUS_DAILY_BUDGET_USD=1.0
export JT_RESERVE_USD_PER_REAL=0.05
export JT_RATE_LIMIT_PER_MIN=8
export JT_MAX_CONCURRENT_REAL=2
export JT_MAX_MODEL_CALLS=5
export JT_TRUSTED_PROXY=0   # set 1 only behind a trusted reverse proxy
export JT_QUOTA_DB_PATH=/var/lib/junctiontrace/nebius_daily_quota.sqlite
export PYTHONPATH=src:.
```

Startup **refuses** if token missing/weak or OF ≠ mock.

## 2. Start (single worker)

```bash
pip install "python-dotenv>=1.0" "requests>=2.31" "pyyaml>=6" "Flask>=2.3" gunicorn
# IMPORTANT: workers=1 — quota DB is process-local SQLite with BEGIN IMMEDIATE
gunicorn -w 1 -b 0.0.0.0:8080 "api.app:create_app()"
```

## 3. Judge access

1. Open `https://<host>/`
2. Paste `SDN_API_TOKEN` into the session-only token field
3. Use **Safe offline** freely; use **Real Nebius** sparingly (quota reserved per call)
4. Legacy `/api/v1/hackathon/run` and `/investigate` return **410** on hosted
5. Product path: `POST /api/v1/hackathon/multistep`

## 4. What the quota is (and is not)

| Is | Is not |
|----|--------|
| Application estimated daily budget with atomic reserve | Nebius account hard cap |
| Persistent across process restarts (SQLite) | Safe under multi-worker / multi-host |
| Shared by all real-mode model routes | Provider-confirmed invoice |

Monitor: `GET /api/v1/hackathon/capabilities` → `budget` object.

## 5. Local development (unchanged)

Omit `SDN_HOSTED_DEMO`. Loopback works without `SDN_API_TOKEN`.  
Research console: `http://127.0.0.1:8080/research`.
