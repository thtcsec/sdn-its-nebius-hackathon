# Competition delta report — multi-step cyber–physical investigation

**Repo:** `thtcsec/sdn-its-nebius-hackathon` (PRIVATE — visibility unchanged)  
**Branch:** `hackathon/nebius-nvidia`  
**Product story:** A network traffic surge is not always an attack. Investigate physical context before making disruptive decisions.

## What changed (this pass)

| Area | Delivery |
|------|----------|
| Evidence tools | `src/sdn_its/llm/evidence_tools.py` — telemetry, camera metadata, quality, temporal compare, contradictions, human escalate |
| Multi-step loop | `src/sdn_its/llm/multi_step.py` — DETECT → uncertainty → tools → reason → gate → audit |
| Evidence sufficiency gate | `safety.py` blocks **model/planner** containment when physical evidence is insufficient (rules path unchanged) |
| Ablation A/B/C/D | `scripts/run_ablation_study.py` + `ablation.py` on identical held-out inputs |
| Demo scenarios (≥4) | `datasets/hackathon/scenarios/` + console multi-step board |
| API | `/api/v1/hackathon/multistep`, scenarios on `/incidents` |
| Docs | README status fixed; JUDGE_DEMO / DEMO_VIDEO / PUBLIC_RELEASE_CHECKLIST updated |

**Not claimed:** live RTSP inference, production ITS deployment, live OpenFlow switch pushes, or that offline planner outputs are live Nemotron.

## Reproduce

```powershell
cd D:\tu_projects\sdn-its-nebius-hackathon
$env:PYTHONPATH="$PWD\src;$PWD"
python -m pytest tests/test_multi_step_agent.py tests/test_hackathon_agent.py tests/test_nebius_llm.py tests/test_heldout_eval.py -q
python scripts/run_multistep_demo.py
python scripts/run_ablation_study.py --skip-real --allow-containment-in-demo
# optional live (≤ $0.10):
python scripts/run_ablation_study.py --real-limit 3 --budget-usd 0.10 --allow-containment-in-demo --out artifacts/hackathon/ablation_with_real.json
python scripts/verify_nebius_nemotron.py
python scripts/scan_secrets_and_license.py
```

## Multi-step scenarios (traces)

Artifact: `artifacts/hackathon/multistep_demo_traces.json` (offline planner + real tools).

| Scenario | Intent |
|----------|--------|
| `scenario_rush_vs_attack` | Attack label vs rush queue → preserve/observe |
| `scenario_missing_camera` | Insufficient physical evidence → observe + escalate |
| `scenario_loft_stable` | Stable zone + LOFT → soft rate-limit path |
| `scenario_unsafe_blocked` | Synthetic unsafe DROP → gate blocks |

## Ablation results (same held-out N=25)

Scoring: `--allow-containment-in-demo` so advisory containment is visible (OpenFlow remains **mock**). Dev fixtures excluded.

### Offline planner arms (comparable full set)

Source: `artifacts/hackathon/ablation_offline.json`

| Arm | Description | correct_vs_oracle | false_escalation | mean tools |
|-----|-------------|-------------------|------------------|------------|
| **A** | Rule-only FusionEngine | **84%** | **16%** | 0 |
| **B** | Multi-step, network only (+gate) | 64% | 4% | ~3.6 |
| **C** | Multi-step, network + camera (gate skipped) | **88%** | 4% | ~4.5 |
| **D** | Multi-step, network + camera + safety gate | **92%** | **0%** | ~4.5 |

**Interpretation (honest):**

- Adding **camera metadata tools** (C vs B) improves correctness and reduces false escalation vs network-only investigation.
- Full stack **D** (camera + gate) best matches oracle on this synthetic held-out set and drives false escalation to **0%**.
- These offline B/C/D scores use `evidence_class=deterministic_planner` (plus protocol classes) — **not** live Nemotron.
- Do **not** treat this as proof that live Nemotron beats rules at production scale.

### Budgeted live Nebius (additional ≤ $0.10)

Source: `artifacts/hackathon/ablation_real_summary.json`

| Metric | Value |
|--------|-------|
| Est. spend | **~$0.00378** (under $0.10 cap) |
| Model | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` |
| real_api cases / arm | **n=3** (diversified families) |
| B/C/D real_api correct | **3/3** each (small-n; not a superiority claim) |

Ping verify: `artifacts/hackathon/nebius_verify_last.json` / redacted bundle `real_api_evidence_redacted.json` pattern — `evidence_class: real_api`.

## Regression tests

```
pytest tests/test_multi_step_agent.py tests/test_hackathon_agent.py tests/test_nebius_llm.py tests/test_heldout_eval.py -q
→ 31 passed
```

Full suite may require torch in the active environment (research detectors); judge path does not.

## Public-release readiness

See `docs/PUBLIC_RELEASE_CHECKLIST.md`.

| Item | Status |
|------|--------|
| MIT LICENSE | Present |
| Secret scan | `ok: true` |
| Mock OF default | Yes |
| Multi-step demo + ablation artifacts | Yes |
| YouTube &lt;3 min | **TBD** (`docs/DEMO_VIDEO.md`) |
| Public GitHub | **Blocked — needs owner approval** |
| Hosted demo URL | **Not yet** (local judge path documented) |

## Submission requirements map (Devpost)

| Requirement | Status |
|-------------|--------|
| Token Factory runtime + NVIDIA OSS model | **Met** (real_api evidence) |
| Working software | **Met** (local) |
| Public repo + OSS license | **Not met** (private) |
| YouTube &lt;3 min | **Not met** |
| Working demo URL | **Not met** (local only) |
| Pre-existing project explanation | **Met** (`docs/HACKATHON_CONTRIBUTIONS.md`) |
| Track fit | Best Apps and Agents |

## Limitations

- Camera context in judge/demo path is **synthetic metadata**, not live YOLO/RTSP.
- OpenFlow backend is **mock**; no destructive network operations.
- Offline ablation planner is not Nemotron; live sample n=3 is underpowered for ranking claims.
- Repository remains private until explicit approval.
