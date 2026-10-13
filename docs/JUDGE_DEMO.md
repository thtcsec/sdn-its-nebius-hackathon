# Judge demo — Nebius × NVIDIA (SOLO)

## What you are evaluating

A **cyber–physical multi-step investigation agent** for SDN-ITS:

1. DETECT anomaly → identify uncertainty
2. SELECT evidence tools (telemetry, camera metadata quality, temporal compare, contradictions, human escalate)
3. REASON (offline: deterministic planner; real: NVIDIA Nemotron via Nebius Token Factory)
4. Schema validation + deterministic safety gate (evidence sufficiency + de-escalation)
5. PolicyEngine mapping (default OpenFlow = **mock**) + audit trail

**Product story:** A network traffic surge is not always an attack. Investigate physical context before making disruptive decisions.

This is **not** a generic chatbot and **not** a claim that Nemotron beats the rule baseline unless comparable ablation measurements show it. Camera fields in the judge path are **synthetic metadata**, not live RTSP.

## What you do **not** need

- Private RTSP URLs / `1.cameras.json`
- Research `tcn_gru_best.pt` checkpoint (console may show `MODEL · DEGRADED` — expected)
- Live Mininet / real switch installs

## Quick start (offline, reproducible)

### A) Lightweight judge scripts (no torch)

Enough for fixtures → rules → synthetic/real Nemotron path scripts:

```powershell
cd D:\tu_projects\sdn-its-nebius-hackathon
py -m venv .venv-judge-light
.\.venv-judge-light\Scripts\activate
pip install "python-dotenv>=1.0" "requests>=2.31" "pyyaml>=6" "Flask>=2.3" "pytest>=7"
$env:PYTHONPATH="$PWD\src;$PWD"
python scripts/run_judge_demo.py
python scripts/run_multistep_demo.py
python scripts/generate_heldout_eval.py
python scripts/run_heldout_eval.py --skip-real
python scripts/run_ablation_study.py --skip-real
python scripts/run_hackathon_benchmark.py --mode offline --allow-containment-in-demo
pytest tests/test_hackathon_agent.py tests/test_nebius_llm.py tests/test_heldout_eval.py tests/test_multi_step_agent.py -q
```

Held-out oracle eval: `datasets/hackathon/eval/` — disjoint from regression fixtures.  
Demo scenarios (multi-step stories): `datasets/hackathon/scenarios/`.  
Ablation A/B/C/D: `python scripts/run_ablation_study.py --skip-real`  
Budgeted live Nebius (≤ $0.10): `python scripts/run_ablation_study.py --real-limit 3 --budget-usd 0.10 --allow-containment-in-demo`


### B) Full package + console (includes torch)

```powershell
py -m venv .venv-judge
.\.venv-judge\Scripts\activate
pip install -e ".[dev]"
pytest -q
.\scripts\dev.ps1
```

Artifacts:

- `artifacts/hackathon/judge_demo_last.json` (gitignored pattern `*_last.json`)
- `artifacts/hackathon/benchmark_offline.json` (tracked when you run offline benchmark)

## Real Nebius mode (optional)

Create repo-root `.env` (gitignored):

```env
NEBIUS_API_KEY=...
NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1
NEBIUS_MODEL=nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B
```

```powershell
python scripts/verify_nebius_nemotron.py
python scripts/run_judge_demo.py --real
```

Forced fixtures (`05_malformed`, `06_unavailable`) still fail closed even in `--real`.

## Console UI

```powershell
.\scripts\dev.ps1
# → http://127.0.0.1:8080/
```

Use the **Hackathon · Incident agent** board:

- Multi-step scenarios + regression fixtures
- Telemetry + synthetic camera metadata
- Investigation trace (tools → gate → audit)
- **Investigate (multi-step)** / offline / real Nebius

## Acceptance map

| Criterion | How to verify |
|-----------|----------------|
| Real Nemotron works | `verify_nebius_nemotron.py` → `evidence_class: real_api` |
| ≥4 multi-step scenarios | `run_multistep_demo.py` + `datasets/hackathon/scenarios/` |
| Fair ablation | `ablation_offline.json` arms A–D + honesty_note |
| Honest benchmark | `benchmark_offline.json` summary + honesty_note |
| No private datasets | fixtures/scenarios under `datasets/hackathon/` |
| Unsafe rec cannot bypass gate | `scenario_unsafe_blocked` / fixture `07_*` |
| Missing camera abstains | `scenario_missing_camera` → observe |

## License

MIT — see [LICENSE](../LICENSE).
