# Judge demo — Nebius × NVIDIA (SOLO)

## What you are evaluating

A **cyber–physical incident investigation agent** for SDN-ITS:

1. Deterministic rule fusion (network label × same-zone camera metadata)
2. NVIDIA Nemotron advisory investigation via Nebius Token Factory
3. Schema validation + deterministic safety gate
4. PolicyEngine mapping (default OpenFlow = **mock**)

This is **not** a generic chatbot and **not** a claim that Nemotron beats the rule baseline unless the offline/real benchmark shows it.

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
python scripts/run_hackathon_benchmark.py --mode offline --allow-containment-in-demo
pytest tests/test_hackathon_agent.py tests/test_nebius_llm.py -q
```

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

- Telemetry + synthetic camera context
- Rule-only vs Nemotron validated action
- Gate / audit history
- **Run offline** or **Run real Nebius**

## Acceptance map

| Criterion | How to verify |
|-----------|----------------|
| Real Nemotron works | `verify_nebius_nemotron.py` → `evidence_class: real_api` |
| ≥4 scenarios E2E | `run_judge_demo.py` |
| Honest benchmark | `benchmark_offline.json` summary + honesty_note |
| No private datasets | fixtures under `datasets/hackathon/incidents/` |
| Unsafe rec cannot bypass gate | fixture `07_unsafe_escalation_blocked` |

## License

MIT — see [LICENSE](../LICENSE).
