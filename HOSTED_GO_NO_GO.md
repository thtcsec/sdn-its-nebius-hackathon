# JunctionTrace — Hosted Security Gate — GO / NO-GO

**Branch:** `hackathon/nebius-nvidia`  
**Date (UTC):** 2026-10-20 (rehearsal re-run; same engineering GO)  
**Engineering verdict:** **GO** for single-worker, token-gated, mock-OF hosted judge demo  

**Competition / Devpost verdict:** **BLOCKED** — see `SUBMISSION_READY.md`.  
Engineering GO is **not** proof of public host, public repo, YouTube, or Devpost readiness.

**Explicitly NOT done / NOT authorized:** cloud host live, public visibility flip, YouTube publish, Devpost submit, API key creation/exposure.

---

## Acceptance checklist (P0) — engineering gate

| # | Criterion | Result |
|---|-----------|--------|
| 1 | Missing hosted token → startup rejection | **PASS** |
| 2 | Unauthorized model requests → 401 | **PASS** |
| 3 | Every model endpoint shares quota | **PASS** |
| 4 | Legacy routes cannot disable hosted safety | **PASS** |
| 5 | No real switch containment | **PASS** (mock OF) |
| 6 | Budget exhaustion blocks before model | **PASS** |
| 7 | Process restart does not reset daily quota | **PASS** (incl. crash orphans charged) |
| 8 | Concurrent requests cannot bypass reserve/inflight | **PASS** |
| 9 | Spoofed X-Forwarded-For does not bypass rate limits | **PASS** |
| 10 | Authorized offline + live judge flows work | **PASS** (live requires server-side key; not CI) |
| 11 | Research accessible locally | **PASS** |
| 12 | CI / browser tests continue | **PASS** (credential-free light CI) |
| 13 | `.env.example` placeholder tokens rejected | **PASS** (`token_is_secure`) |

---

## Remaining blockers (not security-gate failures)

1. **Hosted URL not deployed** — local Docker smoke ≠ public host  
2. **YouTube not uploaded** — canonical local file `junctiontrace_REAL_APP_DEMO.mp4` (75.6 s, gitignored)  
3. **Repo still private** — visibility needs owner approval  
4. **Devpost not submitted**  
5. Multi-worker quota replication unsupported (by design)  
6. Application daily quota is **not** a Nebius provider hard spending cap  

---

## Remote / CI (verified)

| Item | Value |
|------|-------|
| **Application SHA** | `47dc614d52ab89f37518821006d07bfb85bcd71e` |
| **Security-fix SHA** (in ancestry) | `000354720adb422659e5a11cbf9603f49951bcbd` |
| CI on `47dc614` | https://github.com/thtcsec/sdn-its-nebius-hackathon/actions/runs/39440953197 — **success**, **78 passed** |
| Fix CI run | https://github.com/thtcsec/sdn-its-nebius-hackathon/actions/runs/39257990678 — **success** on `0003547` |
| Workflow | `hackathon-light` → branch `hackathon/nebius-nvidia`; `NEBIUS_API_KEY=""` |

**CI does not execute live Nemotron / Token Factory inference.** Credential-dependent e2e remains local/owner-run.

**Do not claim the host or public release is complete.** Local Docker smoke ≠ cloud host.
