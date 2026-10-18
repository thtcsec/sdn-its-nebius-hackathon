# Hosted security & budget policy (JunctionTrace)

**Status:** Fail-closed hosted gate implemented. See `docs/HOSTED_RUNBOOK.md`.  
Do not provision paid infra or flip repo visibility without owner approval.

## Shared guard architecture

```
Client → middleware (SDN_API_TOKEN on mutating + audit GET)
       → route handler
           → resolve_request_safety_flags()  # demo/gate/containment/apply_policy
           → begin_real_if_needed()          # SQLite atomic reserve + rate + concurrency
           → model call (only if admitted)
           → finish_real() / settle()
```

| Route | Hosted (`SDN_HOSTED_DEMO=1`) | Local research |
|-------|------------------------------|----------------|
| `POST .../multistep` | Token + policy + quota | Quota on `mode=real` |
| `POST .../run` | **410 disabled** | Open; policy if token; quota on real |
| `POST .../investigate` | **410 disabled** | Open; policy if token; always quota (model path) |
| `GET .../audit` | Token required | Token if configured |

## Fail-closed startup (`SDN_HOSTED_DEMO=1`)

- Missing / weak `SDN_API_TOKEN` → `HostedConfigError` (process does not serve)
- `SDN_OF_BACKEND` must be `mock`
- Forces `demo_mode=true`, `apply_gate=true`, `allow_containment_in_demo=false`, `apply_policy=false`

## Quota (application-level)

- SQLite file (`JT_QUOTA_DB_PATH`), `BEGIN IMMEDIATE` admission
- Conservative per-request reserve (`JT_RESERVE_USD_PER_REAL`) before inference
- Survives process restart; single-worker only
- Reports `estimated_spent_usd` vs `confirmed_spent_usd` (confirmed usually 0 unless wired)
- **Not** a Nebius provider hard spending cap

## Rate-limit identity

- Default: `remote_addr` only (ignore client `X-Forwarded-For`)
- `JT_TRUSTED_PROXY=1`: use left-most XFF hop when behind a trusted proxy

## Honesty

Never claim absolute provider spend control unless Nebius enforces it at the account.
