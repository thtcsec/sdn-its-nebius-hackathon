# Reproducibility & Evidence Guide

This project is an **IEDE research prototype**, not a production ITS controller.
This document states what ships in the repo, how to rebuild tables, and how to
tell **MODEL** output from **SIMULATION**.

## What is in git

| Path | Purpose |
|------|---------|
| `artifacts/models/model_card.json` | Checkpoint metadata (weights may be local-only) |
| `artifacts/results/exp_insdn/` | InSDN classifier-head metrics + confusion matrix |
| `artifacts/results/cross_dataset/` | CIC zero-shot / adapted metrics |
| `artifacts/results/ablation/` | Sweep JSON if present |
| `results/tcn_gru/`, `results/cross_dataset/`, … | Same evidence under `results/` |
| `datasets/manifests/datasets.json` | Dataset inventory + prepare commands |
| `datasets/sample/` | Small CSVs for smoke tests |
| `benchmark/`, `experiments/`, `docker/`, `.github/` | Code + configs as documented |

**Not in git (by design):** `.venv`, `datasets/raw/`, large `*.npz`, `*.pt` checkpoints.
Train locally or pack with `.\scripts\package.ps1 -IncludeCheckpoint`.

Split / metrics honesty: see [METHODOLOGY.md](METHODOLOGY.md). Re-run
`prepare_data` → `train` → `evaluate` → `sync_artifacts.ps1` after the
`rows_before_window_v1` protocol before treating Acc/F1 as final. Cross-dataset
name is **CIC-IDS2017** (`cicids2017`).

## One-command paper tables

```powershell
# After: pip install -e ".[dev]" and datasets prepared
.\reproduce.ps1
```

Requires:

1. `models/checkpoints/tcn_gru_best.pt` (train first)
2. Prefer `datasets/processed/insdn_windows.npz`

Then sync mirrors:

```powershell
.\scripts\sync_artifacts.ps1
```

## Console honesty modes

| Mode | When | Meaning |
|------|------|---------|
| `MODEL` | Checkpoint loaded | Inference from TCN-GRU weights |
| `SIMULATION` | Demo fallback, no weights | Scripted RE / labels for UI only — **not evidence** |
| `DEGRADED` | Lab mode + no checkpoint | Inference disabled; no fake scores |

Every `/api/v1/infer` response includes:

- `ground_truth` — scenario injector label (if any)
- `prediction` / `predicted_label` — model (or null if degraded)
- `correct` — GT vs prediction (null if overridden/simulated)
- `source` — `model` \| `scenario_simulator` \| `none`
- `preprocess_mode` — `fitted_standard_scaler` or `per_window_zscore_DEMO_MISMATCH`
- `banner` — human-readable warning when not scientific

**Lab mode** (Settings → Lab mode, or default runtime): disables scenario label override
and simulation fallback. Prefer this for reviews.

## Citing metrics

Prefer **classifier-head** binary metrics from:

- `artifacts/results/exp_insdn/metrics.json`
- `artifacts/results/cross_dataset/adapted_metrics.json`

Do **not** lead with synthetic multiclass 100% — that mainly shows the generator is separable.
Do **not** present mock OpenFlow policy latency as full network \(T_{\text{response}}\) without a lab dump.

## OpenFlow reality levels

| Backend | Env | Reality |
|---------|-----|---------|
| `mock` | default Windows | Print / in-memory only |
| `queue` | dry-run | In-memory flow-mod log |
| `http` / `wsl` | `SDN_OF_BACKEND=http` + `scripts/wsl_of_agent.py` | Real `ovs-ofctl` on Mininet bridges |
| `ryu` | Linux/WSL + Ryu | Real datapath path (lab) |

See [lab_checklist.md](lab_checklist.md).

## Submission zip

```powershell
.\scripts\sync_artifacts.ps1
.\scripts\package.ps1
```

Zip must contain the same tree as this README (`benchmark/`, `experiments/`, `results/` metrics, `artifacts/`, …).
