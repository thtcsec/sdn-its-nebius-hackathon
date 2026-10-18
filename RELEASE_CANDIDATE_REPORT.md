# JunctionTrace — Release Candidate Report

**Branch:** `hackathon/nebius-nvidia`  
**Date (UTC):** 2026-10-18  
**Verdict:** **CONDITIONAL GO** for judge-facing demo on a cost-capped, token-gated host  
**Not authorized by this report:** public visibility flip, paid infra provision, YouTube upload, Devpost submit

---

## 1. What was verified (this sprint)

| Gate | Result | Evidence |
|------|--------|----------|
| Multistep + audit require `SDN_API_TOKEN` when configured | PASS | `tests/test_hackathon_security.py` |
| Rate / concurrency / daily budget reject **before** model | PASS | same + `hackathon_guard.py` |
| Hosted demo policy ignores client `demo_mode=false` / containment | PASS | same |
| Timeout → fail-closed `observe` | PASS | API + security test |
| Malformed input 400 | PASS | security test |
| DOM XSS: no `innerHTML`; malicious rationale stays text | PASS | Playwright `dom_xss_textcontent_safe` |
| Playwright does not PASS on blocked / missing creds | PASS | `scripts/e2e_product_ui.py` (SKIPPED path) |
| Real Nebius `evidence_class=real_api` with tools + conclusion | PASS | E2E + `artifacts/hackathon/real_nemotron_trace_loft_stable.json` |
| Scenario B honesty (not “Credible cyberattack”) | PASS | UI label + scenario JSON |
| Landing density @ 1440×900 (scenarios in first viewport) | PASS | `y≈528` for first scenario card |
| `/research` preserved | PASS | E2E + `test_product_ui.py` |
| OpenFlow mock | PASS | capabilities + response `of_backend` |

---

## 2. Remote / CI (fill after push)

| Item | Value |
|------|-------|
| Remote commit SHA | _pending push_ |
| GitHub Actions | _pending_ — job `hackathon-light` must be green |
| Security pytest | 25 passed locally (`test_hackathon_security` + `test_product_ui` + `test_security`) |

---

## 3. Playwright summary (local, credentials present)

| Bucket | PASS | FAIL | SKIPPED |
|--------|------|------|---------|
| deterministic | 12 | 0 | 0 |
| mocked | 2 | 0 | 0 |
| real_api | 1 | 0 | 0 |

- **Exit code:** 0  
- **Report:** `artifacts/hackathon/e2e_product_report.json`  
- **Screens:** `artifacts/hackathon/product_screens/01_landing_1440x900.png`, `04_complete_real_1440x900.png`, `06_mobile_390x844.png`  
- CI without `NEBIUS_API_KEY`: `real_nebius_path` must be **SKIPPED**, not PASS.

---

## 4. Real Nemotron trace (Scenario B)

File: `artifacts/hackathon/real_nemotron_trace_loft_stable.json`

| Field | Value |
|-------|--------|
| evidence_class | `real_api` |
| Nemotron action | `observe` |
| Rule-only action | `rate_limit` |
| Tools | inspect_camera_metadata, compare_temporal_windows, identify_contradictions |
| OF | mock |
| Cost (this capture) | ~$0.001 |

**Story:** Quiet zone + low-rate anomaly — rule-only tends to soft-contain; live investigation may observe when evidence is thin. Model variability is expected; full trace is the product.

**Also demo:** Scenario A legitimate congestion — offline path shows avoiding unnecessary containment.

---

## 5. Hosted security configuration

See `docs/HOSTED_SECURITY.md` and `.env.example`.

Minimum hosted env:

```text
NEBIUS_API_KEY=<server>
SDN_API_TOKEN=<judge-shared>
SDN_HOSTED_DEMO=1
NEBIUS_DAILY_BUDGET_USD=1.0
JT_RATE_LIMIT_PER_MIN=8
JT_MAX_CONCURRENT_REAL=2
SDN_BIND_HOST=0.0.0.0
```

Judge pastes token into session-only UI field. Keys never leave the server.

---

## 6. Research vs hackathon

| Layer | Location |
|-------|----------|
| Pre-existing research console | `/research` · IEDE / SDN-ITS lab UI |
| New hackathon product | `/` · JunctionTrace |
| New security guards | `hackathon_guard.py`, token on multistep/audit |

Details: `docs/HACKATHON_CONTRIBUTIONS.md`

---

## 7. AI vs deterministic baseline (honest)

From prior blind / ablation work (not re-run as a full study in this sprint):

- Offline planner (B) remains a strong baseline; often matches or exceeds live Nemotron on small held-out sets for action accuracy.
- Nemotron value in the product is **tool selection + labeled `real_api` conclude + full trace**, not a blanket accuracy win.
- Do **not** advertise offline planner accuracy as Nemotron accuracy.
- Scenario B illustrates useful disagreement: rule `rate_limit` vs model `observe` under thin evidence.

---

## 8. Video storyboard

`docs/DEMO_VIDEO.md` — &lt;3 min JunctionTrace path. **Not recorded/uploaded** (needs owner approval).

---

## 9. GO / NO-GO

| Question | Answer |
|----------|--------|
| Safe for private judge demo with token + budget? | **GO** (CONDITIONAL) |
| Safe to make repo public / deploy paid / submit Devpost? | **NO-GO** until owner approval + checklist in `docs/PUBLIC_RELEASE_CHECKLIST.md` |
| Remaining human steps | Deploy host, share judge token, record YouTube, visibility/Devpost only if approved |

**CONDITIONAL GO** means: engineering controls for the P0 audit items are in place and locally verified; release packaging still requires owner decisions outside this sprint.
