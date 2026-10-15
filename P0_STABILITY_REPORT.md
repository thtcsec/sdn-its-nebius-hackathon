# P0 Stability + Model Reliability Rescue

**Branch:** `hackathon/nebius-nvidia`  
**Base (pre-rescue report push):** `419d1a2` (JUDGE_ACCEPTANCE_REPORT + blind set)  
**This rescue tip:** `319076b13d8e6875a7faa20ff9f559947e515454`  

## Mission A — Robustness

- Added `src/sdn_its/llm/input_sanitize.py` (safe float/bool/int; telemetry/camera sanitize).
- `FusionEngine.fuse` fail-closes to **observe** on untrusted/NaN/non-numeric fields (never crash, never contain).
- Evidence tools sanitize before `float()`; temporal compare returns controlled failure if PIN unusable.
- Multi-step / rule-only paths sanitize on ingress.

**Proof:** `tests/test_input_sanitize.py`; `p0_regression_eval.json` → `unreliable_no_crash: true`.

## Mission B — Structured model outputs

- Root cause: reserved conclude accepted any truthy `recommended_action` (including `"..."`) before schema validation.
- Fix: `_schema_accept` + validate before accepting conclude; **at most one** repair prompt listing `ALLOWED_ACTIONS`.
- Placeholders / unknown verbs are **not** coerced into containment (`block`/`drop`/`...` → reject).
- Safe aliases only for explicit spellings (`preserve`→`preserve_rush_hour`, `rate-limit`→`rate_limit`).
- Failed model conclude → `deterministic_fallback` labeled separately (not `nemotron_conclude`).

**Proof:** `tests/test_schema_repair.py`; live P0: `C_validation_error_rate=0`, `C_nemotron_conclude_rate=1.0`.

## Mission C — AI value (honest)

Prior blind gap (unchanged oracles):

1. `blind_attack_quiet_road` — model emitted `"..."` → validation fail; planner chose `rate_limit`.
2. `blind_contradict_*` — tools ran (`real_api`) but conclude was fallback — tool value without conclude credit.

Post-fix regression (`scripts/run_p0_regression_eval.py`, budget ≤$0.10, spend ≈ **$0.0043**):

| Metric | Value |
|--------|-------|
| A rules correct | 0.75 |
| B planner correct | **1.0** |
| C Nemotron correct | **1.0** |
| D gate replay correct | **1.0** |
| C nemotron_conclude rate | 0.75 |
| C fallback rate | 0.25 |
| C validation_error rate | **0.0** |
| C containment rate | 0.25 |
| C mean latency | ~12 s |
| C mean tool calls | 3.0 |
| unreliable_no_crash | **true** |

**Browser (local console):** `scenario_loft_stable` → Run real Nebius → `mode: real`, `evidence_class=real_api`, `nemotron_conclude`, tools=3, action=`observe`, latency≈11s, OF=mock.

**Honest read:** Engineering NO-GO for crashes/placeholder conclude is **resolved**. On this small regression set C matched B at 100% correct, but B remains the stronger offline baseline in the larger blind study; Nemotron value is **tool selection + labeled conclude**, with fallback still possible (25% here).

## Mission D — CI

- Workflow: `.github/workflows/hackathon-light.yml` on `hackathon/nebius-nvidia`.
- Light deps + targeted pytest (incl. sanitize/schema tests).

**CI URL / result:** https://github.com/thtcsec/sdn-its-nebius-hackathon/actions/runs/38766235602 — **success** (head `319076b`)

## Mission E — Working app + hosted plan

- Local console: `python -m api.app --host 127.0.0.1 --port 8080`
- Hosted plan: `docs/HOSTED_DEMO_PLAN.md` (cost-limited; mock OF; no visibility flip without approval).

## Remaining release blockers

1. Repo still **private**  
2. No public YouTube demo recording  
3. No hosted judge URL live yet  
4. Devpost submit still needs owner approval  

Engineering crash / invalid-action NO-GO items from the judge report are addressed; administrative eligibility is not.
