# AI-Assisted Resilience for SDN-Enabled Intelligent Transportation Systems (`sdn-its-resilience-ai`)

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![PyTorch 2.0+](https://img.shields.io/badge/PyTorch-2.0%2B-ee4c2c.svg)](https://pytorch.org/)
[![SDN Framework](https://img.shields.io/badge/SDN-Ryu%20%7C%20ONOS-green.svg)](https://ryu.readthedocs.io/)
[![Simulation](https://img.shields.io/badge/Simulation-Mininet--WiFi%20%7C%20SUMO-orange.svg)](https://mininet-wifi.github.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Academic Context](https://img.shields.io/badge/Tsinghua%20IEDE-Autumn%202026-purple.svg)](docs/IEDE_Report_Summary.md)

> **A Lightweight Research Framework for V2X Network Reliability, Edge Telemetry, and Safety-Aware SDN Mitigation**  
> **Research Proposal Project** | Tsinghua University Innovation and Entrepreneurship Development Education  
> **Author:** Trinh Hoang Tu  
> **Project Advisor:** Prof. Kris Singh (Visiting Professor at Tsinghua University; CEO at SRII, Silicon Valley)

---

## Executive Summary

Intelligent Transportation Systems (ITS) depend on V2X, RSUs, edge nodes, and SDN. Centralized control creates **control-plane overload** (`packet_in` floods / LOFT), **safety-critical latency** constraints, and a **resilience gap** when permanent blocking disrupts legitimate rush-hour traffic.

This repository is structured as a **research framework** (not a flat student script dump):

1. **Flow-level telemetry** (non-DPI counters)  
2. **Hybrid TCN-GRU** anomaly detection with adaptive \(\tau = \mu_{RE} + k\sigma_{RE}\)  
3. **Detect → Contain → Rollback** mitigation with cooldown  

Pipeline: **Vehicle → RSU → OVS → Controller → Telemetry → AI → Mitigation → Rollback**

Docs: [architecture](docs/ARCHITECTURE.md) · [dataset](docs/dataset.md) · [experiments](docs/experiments.md) · [api](docs/api.md) · [deployment](docs/deployment.md)

---

## Repository Structure

```text
sdn-its-resilience-ai/
├── docs/                 # Architecture, API, datasets, experiments, roadmap
├── configs/              # YAML configs (train / evaluate / controller / simulation)
├── datasets/             # raw / processed / synthetic / sample (no large commits)
├── src/sdn_its/
│   ├── ai/               # TCN-GRU + Transformer train / eval / quantize / infer
│   ├── telemetry/        # Features, window buffer, normalizer
│   ├── controller/       # Flow manager, REST glue, Ryu/OVS stubs
│   ├── mitigation/       # Containment, rollback, cooldown, policy
│   ├── simulation/       # Topology, traffic generator, Scapy
│   └── utils/
├── api/                  # Flask routes, schemas, middleware
├── dashboard/            # Command Center UI
├── benchmark/            # CPU / latency / memory / throughput
├── experiments/          # exp01_normal … exp05_drl
├── models/               # checkpoints / quantized / exported
├── notebooks/
├── visualization/
├── results/  logs/  assets/
├── scripts/              # setup, demo, experiments, packaging
├── tests/
├── docker/
└── .github/workflows/
```

---

## Quickstart

```bash
git clone https://github.com/thtcsec/sdn-its-resilience-ai.git
cd sdn-its-resilience-ai
py -m venv .venv
# Windows: .\.venv\Scripts\activate
pip install -e ".[dev]"
```

### 1-click demo (Windows)

```powershell
.\scripts\dev.ps1
```

Or cross-platform:

```bash
python scripts/run_demo.py
```

Open `http://127.0.0.1:8080/`.

### Train / evaluate / quantize

```bash
# Download REAL InSDN (~141MB, Hugging Face — no Kaggle token)
python scripts/download_dataset.py --name insdn --prefer hf --prepare

# Train on full processed windows (~50k from InSDN) — preferred over 800-row sample
python -m sdn_its.ai.train --npz datasets/processed/insdn_windows.npz --epochs 15
python -m sdn_its.ai.evaluate --npz datasets/processed/insdn_windows.npz
python -m sdn_its.ai.quantize

# Optional ablation: Temporal Transformer
python -m sdn_its.ai.train --arch transformer --npz datasets/processed/insdn_windows.npz --epochs 15
python -m sdn_its.ai.compare --npz datasets/processed/insdn_windows.npz
```

Dataset docs: [docs/dataset.md](docs/dataset.md) · config: [configs/dataset.yaml](configs/dataset.yaml)

### Experiments / sweeps / export

```bash
python scripts/run_experiment.py --exp exp02_ddos
python scripts/run_experiment.py --exp exp05_drl
python scripts/run_sweep.py --epochs 3 --samples 800
python -m sdn_its.ai.export_onnx --format both
python -m benchmark.run_all
```

Ops console extras: Settings (theme / role / online τ / webhook), scenario **Replay**, live infer, feature attribution, export report.

### Tests

```bash
pytest -q
```

---

## Empirical Performance (summary)

| Metric | FP32 | INT8 |
|--------|------|------|
| Model size | 0.981 MB | **0.174 MB** (−82%) |
| Anomaly accuracy | **97.33%** | **97.33%** |
| \(T_{\text{response}}\) | ~9.9 ms | ~10.7 ms |

Full tables and methodology: [docs/benchmark.md](docs/benchmark.md), [docs/IEDE_Report_Summary.md](docs/IEDE_Report_Summary.md).

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
