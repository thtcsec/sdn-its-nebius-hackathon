# JunctionTrace — Hosted Security Gate — GO / NO-GO

**Branch:** `hackathon/nebius-nvidia`  
**Date (UTC):** 2026-10-19  
**Verdict:** **GO** for single-worker, token-gated, mock-OF hosted judge demo (engineering gate)  

**Explicitly NOT done / NOT authorized:** cloud host live, public visibility flip, YouTube publish, Devpost submit.

---

## Acceptance checklist (P0)

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
| 10 | Authorized offline + live judge flows work | **PASS** |
| 11 | Research accessible locally | **PASS** |
| 12 | CI / browser tests continue | **PASS** |
| 13 | `.env.example` placeholder tokens rejected | **PASS** (`token_is_secure`) |

---

## Remaining blockers (not security-gate failures)

1. **Hosted URL not deployed** — local Docker smoke ≠ public host  
2. **YouTube not uploaded** — local MP4+VO only  
3. **Repo still private** — visibility needs owner approval  
4. **Devpost not submitted**  
5. Multi-worker quota replication unsupported (by design)

---

## Remote / CI

| Item | Value |
|------|-------|
| Commit SHA | _updated after this fix push_ |
| GitHub Actions | _updated after this fix push_ |

**Do not claim the host or public release is complete.**
