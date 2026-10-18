# JunctionTrace — Hosted Security Gate — GO / NO-GO

**Branch:** `hackathon/nebius-nvidia`  
**Date (UTC):** 2026-10-18  
**Verdict:** **GO** for single-worker, token-gated, mock-OF hosted judge demo  

**Explicitly NOT authorized by this document:** public visibility flip, paid infra provision, YouTube publish, Devpost submit (owner approval required).

---

## Acceptance checklist (P0)

| # | Criterion | Result |
|---|-----------|--------|
| 1 | Missing hosted token → startup rejection | **PASS** (`HostedConfigError` / `create_app`) |
| 2 | Unauthorized model requests → 401 | **PASS** (multistep / run / investigate) |
| 3 | Every model endpoint shares quota | **PASS** (shared `admit_real`; hosted disables legacy) |
| 4 | Legacy routes cannot disable hosted safety | **PASS** (410 on hosted; policy forced when token set) |
| 5 | No real switch containment | **PASS** (hosted requires `SDN_OF_BACKEND=mock`; `apply_policy` forced off) |
| 6 | Budget exhaustion blocks before model | **PASS** (mocked provider never called) |
| 7 | Process restart does not reset daily quota | **PASS** (SQLite persistence test) |
| 8 | Concurrent requests cannot bypass reserve/inflight | **PASS** (threaded admit test) |
| 9 | Spoofed X-Forwarded-For does not bypass rate limits | **PASS** (identity = `remote_addr` by default) |
| 10 | Authorized offline + live judge flows work | **PASS** (pytest + Playwright real_api) |
| 11 | Research accessible locally | **PASS** (`/research` without hosted flag) |
| 12 | Prior CI / browser tests continue | **PASS** (31 credential-free pytest; 15/15 Playwright) |

---

## Shared guard architecture

- **Module:** `src/sdn_its/llm/hackathon_guard.py` + `api/hackathon_enforce.py`
- **Admission:** SQLite `BEGIN IMMEDIATE` → rate check → concurrency → reserve budget → open reservation
- **Settle:** charge `max(estimated, confirmed)` or keep reserve on uncertain failure; release unused
- **Identity:** `ip:<remote_addr>`; XFF only if `JT_TRUSTED_PROXY=1`
- **Route coverage:**
  - `/multistep` — product path (always)
  - `/run`, `/investigate` — **410** when `SDN_HOSTED_DEMO=1`; otherwise share admit/settle for real/model calls

---

## Evidence

| Kind | Result |
|------|--------|
| Credential-free pytest | `tests/test_hackathon_security.py` + product + security helpers — **31 passed** |
| Mocked-provider | Budget/rate/timeout paths patch Nebius entrypoints — **PASS** |
| Actual Nebius | Playwright `real_nebius_path` — **PASS** (`evidence_class=real_api`) |
| Browser report | `artifacts/hackathon/e2e_product_report.json` |

---

## Remaining blockers (outside this security gate)

These are **release packaging** blockers, not security-gate failures:

1. Hosted URL not deployed (needs owner approval + single-worker host)
2. Demo video not recorded / YouTube not published
3. Repository still private; visibility / Devpost need owner approval
4. Multi-worker / multi-instance quota replication **not** supported (by design)

**Quota honesty:** application estimated daily budget ≠ Nebius account hard cap.

---

## Remote / CI

| Item | Value |
|------|-------|
| Commit SHA | `75a2f239f04f9938339b2696e0aa30dc77391c66` |
| GitHub Actions | https://github.com/thtcsec/sdn-its-nebius-hackathon/actions/runs/39087423749 — **success** |

---

## Next stage (stop engineering)

Deployment → video production → competition submission. **No further feature sprints.**
