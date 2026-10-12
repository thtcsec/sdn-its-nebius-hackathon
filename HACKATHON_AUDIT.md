# Hackathon readiness audit

**Scope:** `D:\tu_projects\sdn-its-nebius-hackathon` only  
**Last updated:** 2026-10-12 — held-out oracle eval + real Nebius subset  
**Baseline before this pass:** `5f793d4`

---

## This pass — held-out evaluation

### Artifacts

| Artifact | Role |
|----------|------|
| `datasets/hackathon/eval/` (25 cases + MANIFEST) | Held-out oracle-labeled set |
| `datasets/hackathon/incidents/` (7) | **Regression only** (not accuracy) |
| `artifacts/hackathon/heldout_eval_rule_only.json` | Full held-out, rule-only + protocol ($0) |
| `artifacts/hackathon/heldout_eval_real_summary.json` | Real Nebius subset metrics (redacted) |
| `artifacts/hackathon/fresh_venv_judge_verify.json` | Fresh light venv OK, no ckpt/RTSP |
| `artifacts/hackathon/secret_license_scan.json` | Hygiene scan |
| `docs/PUBLIC_RELEASE_CHECKLIST.md` | Public flip requires approval |
| `docs/DEMO_VIDEO.md` | &lt;3 min script (URL TBD) |

### Actual metrics (held-out, N=25)

**Rule-only vs oracle**

| Metric | Value |
|--------|-------|
| correct_vs_oracle | **84%** (21/25) |
| false_escalation | **16%** (4/25) — mostly missing-evidence cases where rules still contain |
| unsafe_recommendation | **0%** |
| abstention | 12% |
| mean latency | ~0.25 ms |

**Nemotron real_api subset (N=5, budget $0.05, spent ≈ $0.00130)**

| Metric | Value |
|--------|-------|
| correct_vs_oracle | **80%** (4/5) |
| false_escalation | **20%** (1/5 — `eval_missing_01` chose rate_limit; oracle prefer observe) |
| unsafe_recommendation | **0%** |
| abstention | 20% |
| mean latency | ~4.8 s |
| est. cost | **$0.00130** |

**Protocol probes (malformed / API outage / unsafe escalation):** gate blocked unsafe containment; API outage fail-closed; malformed fail-closed. Not scored as model accuracy.

**Honesty:** Offline synthetic fixture answers are **not** used as held-out accuracy. Skipped rows are `skipped_no_fake_offline`. No claim that Nemotron beats rules (5 live samples only).

### Tests

`66 passed` (full suite).

### Fresh venv

`scripts/verify_fresh_venv_judge.py` → **ok: true**, `checkpoint_present: false`, `camera_inventory_present: false`.

### Secret / license scan

`ok: true` after excluding doc false-positives; `.env` not tracked; LICENSE present.  
**Visibility not changed** (still private).

### Video

Script ready in `docs/DEMO_VIDEO.md`. **Not uploaded** (YouTube URL TBD).

### Remaining blockers

1. Demo video recording/upload  
2. Explicit approval required before public visibility  
3. Larger real_api sample if competition demands stronger AI evidence (costs more)

### Reproduce

```powershell
python scripts/generate_heldout_eval.py
python scripts/run_heldout_eval.py --skip-real
python scripts/run_heldout_eval.py --real-limit 5 --budget-usd 0.05 --allow-containment-in-demo
python scripts/verify_fresh_venv_judge.py
python scripts/scan_secrets_and_license.py
pytest -q
```
