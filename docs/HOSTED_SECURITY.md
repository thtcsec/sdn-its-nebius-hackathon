# Hosted security & budget policy (JunctionTrace)

**Status:** Configuration ready. Do not provision paid infra or flip repo visibility without owner approval.

## Threat model (hackathon demo)

| Risk | Control |
|------|---------|
| Unauthorized Nebius spend via `/api/v1/hackathon/multistep` | `SDN_API_TOKEN` middleware on mutating + audit GET |
| Client disables `demo_mode` / enables containment | `hosted_demo_enforced()` when token or `SDN_HOSTED_DEMO=1` |
| Burst / abuse | `JT_RATE_LIMIT_PER_MIN`, `JT_MAX_CONCURRENT_REAL` |
| Daily overspend | `NEBIUS_DAILY_BUDGET_USD` — reject **before** model call |
| Audit / investigation leakage | Token on `GET /api/v1/hackathon/audit`; compact audit records |
| Live switch damage | OF backend remains **mock**; containment blocked in hosted demo |
| Credential theft | `NEBIUS_API_KEY` server-only; never returned by capabilities |

## Required env (hosted)

```bash
export NEBIUS_API_KEY=...                 # Token Factory — server only
export NEBIUS_MODEL=nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B
export SDN_API_TOKEN=...                  # share with judges only
export SDN_HOSTED_DEMO=1                  # belt-and-suspenders
export SDN_BIND_HOST=0.0.0.0
export NEBIUS_DAILY_BUDGET_USD=1.0        # hard stop
export JT_RATE_LIMIT_PER_MIN=8
export JT_MAX_CONCURRENT_REAL=2
export PYTHONPATH=src:.
```

## Local demo (developer laptop)

Omit `SDN_API_TOKEN` on loopback so offline investigations work without a token.
Real mode still needs `NEBIUS_API_KEY` server-side.

## Judge access model

1. Operator sets `SDN_API_TOKEN` on the host.
2. Judge opens JunctionTrace `/`, pastes token into the session-only field (not localStorage).
3. Offline scenarios work with the token; real Nebius uses the same token + server key.
4. When daily budget or rate limits trip, UI shows the server error — no silent PASS.

## Verify

```bash
pytest -q tests/test_hackathon_security.py tests/test_security.py
# With app running:
# curl -X POST .../multistep  → 401 without token when SDN_API_TOKEN set
```
