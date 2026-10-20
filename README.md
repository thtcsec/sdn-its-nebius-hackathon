# SDN-ITS × Nebius × NVIDIA

**SOLO submission — Nebius x NVIDIA Global AI Hackathon**

Extend **SDN-ITS Resilience AI** (network anomaly detection + reversible mitigation + same-zone camera context) with a **real NVIDIA open-source model** served through **Nebius Token Factory**.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![PyTorch 2.0+](https://img.shields.io/badge/PyTorch-2.0%2B-ee4c2c.svg)](https://pytorch.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Hackathon](https://img.shields.io/badge/Nebius%20x%20NVIDIA-SOLO-0ad4c8.svg)](HACKATHON.md)
[![Repo](https://img.shields.io/badge/GitHub-private-lightgrey.svg)](https://github.com/thtcsec/sdn-its-nebius-hackathon)

**Author:** Trinh Hoang Tu · **Deadline:** 30 October 2026 · **Branch:** `hackathon/nebius-nvidia`

---

## For judges (60-second path)

**JunctionTrace** helps an ITS/SOC operator investigate a traffic surge **before** disruptive containment. Immediate drop/rate-limit on a DDoS-looking label can harm legitimate rush-hour mobility.

1. Open the product UI (`/` — not `/research`).
2. Pick a scenario. **Safe offline** uses a deterministic planner + real tools (never labeled as live Nemotron). **Real Nebius** calls **NVIDIA Nemotron** on **Nebius Token Factory**.
3. Watch the journey: incident → uncertainty → **tool selection** → evidence returned → conclusion → **policy gate** → operator action.
4. Compare rule-only vs investigation. Example: quiet-zone / camera context can change `rate_limit` into `observe`.

**Honesty:** OpenFlow is **mock** — JunctionTrace does **not** push rules onto a real traffic switch. Camera fields are **synthetic metadata**. Offline ~92% is the planner, not Nemotron. Live Nemotron samples are small; latency is ~10–20 s advisory, not real-time control. Hosted demos need the Judge API token field.

Local demo video (gitignored): `artifacts/demo_video/junctiontrace_REAL_APP_DEMO.mp4` (**75.6 s**, real app screen recording). YouTube URL is an owner action. Current status: [`SUBMISSION_READY.md`](SUBMISSION_READY.md).

Quick local run (no torch):

```powershell
pip install "python-dotenv>=1.0" "requests>=2.31" "pyyaml>=6" "Flask>=2.3"
$env:PYTHONPATH="$PWD\src;$PWD"
python -m api.app --host 127.0.0.1 --port 8080
# http://127.0.0.1:8080/
```

Hosted package: `docs/JUDGE_HOSTING.md`. Status: [`SUBMISSION_READY.md`](SUBMISSION_READY.md) (public URL / YouTube still owner actions).

---

## What this repo is

| This repo | Not this repo |
|-----------|----------------|
| Hackathon working copy + public-facing submission target (starts **private**) | The IEDE research tree (`sdn-its-resilience-ai`) |
| Real NVIDIA Nemotron via Nebius Token Factory when `NEBIUS_API_KEY` is set | Fake live-Nemotron responses or invented accuracy |
| Offline deterministic planner labeled as planner, not as Nebius | Treating offline 92% as live Nemotron accuracy |
| Demo mode keeps OpenFlow **mock** — no real traffic-switch control | Proof of live switch PacketIn reduction out of the box |

Research / IEDE source of truth (separate folder, do not mix edits):  
`D:\tu_projects\sdn-its-resilience-ai` · upstream: [thtcsec/sdn-its-resilience-ai](https://github.com/thtcsec/sdn-its-resilience-ai)

Local note: [HACKATHON.md](HACKATHON.md)

---

## Hackathon goals

1. Audit baseline SDN-ITS pipeline (telemetry → detector → policy → rollback).
2. Verify Nebius account, credits, and Token Factory inference access.
3. Land a **successful real runtime** call to an NVIDIA Nemotron model via Nebius.
4. Feed network telemetry + camera physical context into Nemotron-assisted incident investigation.
5. Return **structured, validated** mitigation recommendations.
6. Keep deterministic policy gates and rollback; destructive actions off in demo mode.
7. Benchmark against the existing rule-based baseline (honest deltas only).
8. English docs + YouTube demo under 3 minutes; open-source when ready to publish.

### Status (honest)

**Competition submission: BLOCKED** until public repo, hosted demo URL, public YouTube &lt;3 min, and Devpost — see [`SUBMISSION_READY.md`](SUBMISSION_READY.md). Application tip `47dc614`; light CI [39440953197](https://github.com/thtcsec/sdn-its-nebius-hackathon/actions/runs/39440953197) (78 passed, **no live Nemotron in CI**).

| Milestone | Status |
|-----------|--------|
| Private hackathon repo + isolated working tree | Done |
| Nebius API key / authenticated Token Factory inference | Done when `.env` has `NEBIUS_API_KEY` (see redacted `artifacts/hackathon/`) |
| Minimal vertical slice (real Nemotron Nano) | Done |
| Multi-step evidence investigation (tools + gate + audit) | Done |
| Validated structured mitigation + policy gates | Done |
| Fair ablation A/B/C/D on held-out set | Done (offline planner + optional budgeted real) |
| Local demo video &lt;3 min (h264+aac) | Done locally: `junctiontrace_REAL_APP_DEMO.mp4` 75.6 s (gitignored); **YouTube URL TBD** |
| Public docs + YouTube + hosted demo URL | **Pending owner** |
| Public GitHub visibility | **Pending owner approval** (still private) |

Default model: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`  
API: OpenAI-compatible · `https://api.tokenfactory.nebius.com/v1/` · env: `NEBIUS_API_KEY`

**Product story:** A network traffic surge is not always an attack. Investigate physical context before making disruptive decisions.

---

## Base system (inherited)

Pipeline: **telemetry → anomaly inference → policy (+ optional same-zone camera) → temporary OpenFlow → rollback**.

- Camera = physical-context sensor for the same RSU zone (not a standalone DDoS detector).
- Default OpenFlow backend on Windows is **mock**.
- Evidence / honesty docs from the research baseline: [docs/REPRODUCE.md](docs/REPRODUCE.md) · [docs/EVIDENCE.md](docs/EVIDENCE.md) · [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

Tracked classifier snapshot (InSDN): `artifacts/results/exp_insdn/metrics.json` — cite those files; do not invent improvements.

---

## Quickstart

```powershell
git clone https://github.com/thtcsec/sdn-its-nebius-hackathon.git
cd sdn-its-nebius-hackathon
git checkout hackathon/nebius-nvidia
py -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
```

### Ops console (lab defaults)

```powershell
.\scripts\dev.ps1
# → http://127.0.0.1:8080/
```

Defaults: lab mode on, bind `127.0.0.1`, mock OpenFlow, no silent fake scores.  
LAN: `SDN_BIND_HOST=0.0.0.0` + optional `SDN_API_TOKEN` — [docs/deployment.md](docs/deployment.md).

### Judge demo / Nebius

Judge path (synthetic fixtures, mock OF, no private RTSP/checkpoint): [docs/JUDGE_DEMO.md](docs/JUDGE_DEMO.md)

```powershell
python scripts/run_judge_demo.py
python scripts/run_multistep_demo.py
python scripts/run_ablation_study.py --skip-real
python scripts/run_hackathon_benchmark.py --mode offline --allow-containment-in-demo
```

Real Nebius: put `NEBIUS_API_KEY` in repo-root `.env` (gitignored), then:

```powershell
python scripts/verify_nebius_nemotron.py
```

Create a key: [Nebius Token Factory → API keys](https://tokenfactory.nebius.com/).

---

## Repository layout

```text
sdn-its-nebius-hackathon/
├── HACKATHON.md          # Local isolation note (research tree path)
├── src/sdn_its/          # Detector, telemetry, camera, controller, mitigation
├── api/  dashboard/      # Flask + evidence console
├── configs/              # controller, cameras, train/eval
├── artifacts/ results/   # Tracked metrics from the baseline
├── docs/                 # Architecture, evidence, reproduce (baseline + hackathon)
├── scripts/              # Lab, experiments, (soon) Nebius verify + vertical slice
├── benchmark/ tests/
└── reproduce.ps1
```

---

## Docs index

| Doc | Content |
|-----|---------|
| [HACKATHON.md](HACKATHON.md) | Working-tree isolation |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System layers |
| [docs/EVIDENCE.md](docs/EVIDENCE.md) | Console badges / evidence rules |
| [docs/REPRODUCE.md](docs/REPRODUCE.md) | Rebuild tables, citing rules |
| [docs/api.md](docs/api.md) | REST |
| [docs/lab_checklist.md](docs/lab_checklist.md) | Mininet / OVS (optional) |

---

## Tests

```powershell
$env:CUDA_VISIBLE_DEVICES=""
pytest -q
```

---

## License

MIT — see [LICENSE](LICENSE).

Baseline research lineage: Trinh Hoang Tu · IEDE / Tsinghua context documented in the research repo; this repository is the **hackathon** fork for Nebius × NVIDIA work.
