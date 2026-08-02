# Reversible Mitigation Testbed for SDN-Enabled ITS Edge Networks

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![PyTorch 2.0+](https://img.shields.io/badge/PyTorch-2.0%2B-ee4c2c.svg)](https://pytorch.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Academic Context](https://img.shields.io/badge/Tsinghua%20IEDE-Autumn%202026-purple.svg)](docs/IEDE_Report_Summary.md)

> **Research testbed** (IEDE) — reproducible loop for *safety-aware, reversible* SDN mitigation:  
> telemetry window → inference → policy decision → (optional) OpenFlow install → cooldown rollback.  
> Dashboard is an **evidence console**, not a SOC product. Default OpenFlow on Windows is **mock**.  
> **Author:** Trinh Hoang Tu · **Advisor:** Prof. Kris Singh (Tsinghua visiting / SRII)

---

## What this is / is not

| Is | Is not |
|----|--------|
| **Reversible mitigation** testbed (Detect → temporary contain → rollback) | Proof that controller load / attack pps fell on a real switch |
| Train/eval on **InSDN** + cross-dataset **CIC** adaptation | Claim that TCN-GRU beats simple baselines (current ablation does not) |
| Lab console with honest KPI names + `NET · NO EVIDENCE` when mock | “134 mitigations” = 134 real network attacks |
| Optional real **OVS** via WSL `of_agent` (`SDN_OF_BACKEND=http`) | Default Windows path installing verified OpenFlow rules |
| Tracked **artifacts/results** + event trace IDs | End-to-end ITS latency / PacketIn evidence out of the box |

Honesty & reproduce: [docs/REPRODUCE.md](docs/REPRODUCE.md) · [docs/EVIDENCE.md](docs/EVIDENCE.md) · [docs/lab_checklist.md](docs/lab_checklist.md)

### Camera-assisted fusion (physical context)

Not a video wall and **not** a pile of `CAMERA_*` env vars. Selection is an allow-list:

- `configs/cameras.yaml` — which inventory IDs to load (max 3)
- `1.cameras.json` — local inventory with RTSP URLs (**gitignored**; may hold credentials)
- Worker probes RTSP health; optional single overwritten JPEG under `tmp/camera_frames/` (no history)

```powershell
# Edit select: in configs/cameras.yaml, keep inventory file local
.\.venv\Scripts\python.exe scripts\exp_bc_camera_fusion.py
```

Console: **Camera context** + **Fusion decision** (`GET /api/v1/camera`, `POST /api/v1/camera/reload`).

### Experiment A — DDoS containment (network evidence)

```powershell
# Schema only (Windows CI / no Mininet):
.\scripts\run_exp_a.ps1 -DryRun

# Live Mininet/OVS in WSL (root) — writes exp_a_metrics.json:
.\scripts\run_exp_a.ps1
```

Compares **none / permanent DROP / temporary DROP+rollback** with ICMP delivery ratios + `ovs-ofctl` verify. Console board: `/api/v1/lab/evidence` (Actuation/Outcome grey without network evidence).

---

## Repository layout

```text
sdn-its-resilience-ai/
├── artifacts/            # Paper-facing mirrors (metrics, model_card) — tracked
├── results/              # Eval outputs (tcn_gru, cross_dataset, ablation, …)
├── datasets/
│   ├── sample/           # Small CSVs in git
│   ├── manifests/        # Inventory + prepare commands
│   ├── raw/ processed/   # Large dumps — gitignored; download locally
├── src/sdn_its/          # AI, telemetry, controller, mitigation, simulation
├── api/  dashboard/      # Flask + evidence console
├── benchmark/            # Micro-benchmarks (in repo)
├── experiments/          # exp01–exp05 YAML + folders
├── models/               # checkpoints/ (weights gitignored; .gitkeep + exports meta)
├── notebooks/  visualization/  docker/  .github/
├── docs/                 # Architecture, reproduce, evidence, lab
├── scripts/              # train helpers, lab, package.ps1, sync_artifacts.ps1
├── reproduce.ps1         # Rebuild primary tables
└── tests/
```

---

## Quickstart

```powershell
git clone https://github.com/thtcsec/sdn-its-resilience-ai.git
cd sdn-its-resilience-ai
py -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
```

### Ops console (research defaults)

```powershell
.\scripts\dev.ps1
# → http://127.0.0.1:8080/
```

Defaults: **Lab mode on**, no scenario label cheat, no ambient fake RE, research theme.  
Evidence bar must show `MODEL · LOADED` before treating numbers as real.  
If checkpoint missing → `DEGRADED` (inference disabled), not silent fake scores.

Demo injects that force labels: Settings → disable Lab mode → enable scenario override (UI marks `OVERRIDDEN`).

### Train / evaluate (preferred evidence path)

```powershell
python scripts/download_dataset.py --name insdn --prefer hf --prepare
python -m sdn_its.ai.train --npz datasets/processed/insdn_windows.npz --epochs 15
python -m sdn_its.ai.evaluate --npz datasets/processed/insdn_windows.npz
.\scripts\sync_artifacts.ps1
.\reproduce.ps1   # optional full refresh + run_manifest
```

Cross-dataset:

```powershell
python scripts/download_dataset.py --name cicids2017 --prefer hf --prepare
python scripts/run_cross_dataset.py
python scripts/adapt_to_cic.py --epochs 5 --adapt-ratio 0.2
.\scripts\sync_artifacts.ps1
```

### Real OpenFlow lab (optional but strong)

```powershell
$env:SDN_OF_BACKEND = "http"
# WSL: sudo python scripts/wsl_of_agent.py --port 8089
# then Mininet topology + dump-flows — see docs/lab_checklist.md
```

### Package for submission

```powershell
.\scripts\sync_artifacts.ps1
.\scripts\package.ps1                     # source + metrics (no *.pt)
.\scripts\package.ps1 -IncludeCheckpoint  # include weights
```

---

## Tracked empirical snapshot (classifier head)

Canonical copies live under `artifacts/results/` (refresh via `sync_artifacts.ps1`).

| Eval | Where |
|------|--------|
| InSDN in-domain | `artifacts/results/exp_insdn/metrics.json` |
| CIC zero-shot / adapted | `artifacts/results/cross_dataset/` |
| Ablation JSON | `artifacts/results/ablation/` |

**Cite classifier-head Acc/F1/AUC from those files.**  
Legacy synthetic “97.33% / 100% multiclass” figures in older summary docs are **not** the primary claim — see [docs/REPRODUCE.md](docs/REPRODUCE.md).

Micro-benchmarks / latency methodology: [docs/benchmark.md](docs/benchmark.md).

---

## Docs index

| Doc | Content |
|-----|---------|
| [docs/REPRODUCE.md](docs/REPRODUCE.md) | Rebuild tables, modes, citing rules |
| [docs/EVIDENCE.md](docs/EVIDENCE.md) | Console badges, artifact checklist |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System layers |
| [docs/dataset.md](docs/dataset.md) | InSDN / CIC prepare |
| [docs/lab_checklist.md](docs/lab_checklist.md) | Mininet / OVS |
| [docs/api.md](docs/api.md) | REST |
| [docs/roadmap.md](docs/roadmap.md) | Done / next |

---

## Tests

```powershell
$env:CUDA_VISIBLE_DEVICES=""
pytest -q
```

---

## Citation

```bibtex
@techreport{trinh2026sdnits,
  title        = {AI-Assisted Resilience for SDN-Enabled Intelligent Transportation Systems: A Lightweight Framework for V2X Network Reliability, Edge Telemetry, and Safety-Aware Mitigation},
  author       = {Trinh, Hoang Tu},
  institution  = {Innovation and Entrepreneurship Development Education, Tsinghua University},
  year         = {2026},
  type         = {Research Proposal},
  note         = {Project Advisor: Prof. Kris Singh}
}
```

## License

MIT — see [LICENSE](LICENSE).
