# Experiments

## YAML scenario folders (`experiments/expNN_*`)

| ID | Name | Scenario |
|----|------|----------|
| **exp01** | Normal traffic | Benign V2X baseline |
| **exp02** | Packet Flood | DDoS `packet_in` flood |
| **exp03** | LOFT attack | Low-rate OpenFlow trust probes |
| **exp04** | Rush Hour | Legitimate surge — no persistent block |
| **exp05** | DRL / Rollback | Cooldown rollback + DRL action stub |

```bash
# Needs controller up: python -m api.app
python scripts/run_experiment.py --exp exp02_ddos
python scripts/run_experiment.py --exp exp05_drl

# Ablation (architectures × k·σ) — offline
python scripts/run_sweep.py --epochs 3 --samples 800
```

## Evidence experiments (paper-facing)

Tracked under `artifacts/results/` — prefer these when citing.

| Exp | Script | What it proves | Honesty |
|-----|--------|----------------|---------|
| **A** Containment | `.\scripts\run_exp_a.ps1` (WSL Mininet) | none / permanent DROP / temporary DROP+rollback via ICMP + `ovs-ofctl` | Dry-run on Windows → `network_evidence: false` |
| **B/C** Fusion | `python scripts/exp_bc_camera_fusion.py` | Explainable camera×network policy matrix | Scripted / synthetic physical inputs ≠ live FP reduction |
| **D** Phases | `python scripts/exp_d_camera_containment.py` | Graded tracker × fusion phases | Without `--with-of`, stops at in-memory rules |

See also: [lab_checklist.md](lab_checklist.md), [EVIDENCE.md](EVIDENCE.md), READMEs under `artifacts/results/exp_*`.
