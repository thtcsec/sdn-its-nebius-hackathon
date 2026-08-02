# AI-Assisted Resilience for SDN-Enabled Intelligent Transportation Systems

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![PyTorch 2.0+](https://img.shields.io/badge/PyTorch-2.0%2B-ee4c2c.svg)](https://pytorch.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Academic Context](https://img.shields.io/badge/Tsinghua%20IEDE-Autumn%202026-purple.svg)](docs/IEDE_Report_Summary.md)

> **Research prototype** (IEDE) — flow-level telemetry → TCN-GRU detection → temporary OpenFlow contain/rollback.  
> **Not** a production ITS / SOC product.  
> **Author:** Trinh Hoang Tu · **Advisor:** Prof. Kris Singh (Tsinghua visiting / SRII)

---

## What this is / is not

| Is | Is not |
|----|--------|
| Closed-loop **Detect → Contain → Rollback** research framework | Live RSU / vehicle deployment |
| Train/eval on **InSDN** + cross-dataset **CIC** adaptation | Proof that synthetic 100% multiclass = real attacks |
| Ops console with **Lab mode**, GT vs prediction, MODEL/SIMULATION badges | Silent fake scores presented as inference |
| Optional real **OVS** via WSL `of_agent` | Default Windows path (that is **mock** OpenFlow) |
| Tracked **artifacts/results** metrics for reviewers | A zip of screenshots without code/evidence |

Honesty & reproduce: [docs/REPRODUCE.md](docs/REPRODUCE.md) · [docs/EVIDENCE.md](docs/EVIDENCE.md) · [docs/lab_checklist.md](docs/lab_checklist.md)

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
