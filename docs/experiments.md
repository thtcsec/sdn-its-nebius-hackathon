# Experiments

Each experiment lives under `experiments/expNN_*/` with `config.yaml`, `results/`, `plots/`, and `logs/`.

| ID | Name | Scenario |
|----|------|----------|
| **exp01** | Normal traffic | Benign V2X baseline |
| **exp02** | Packet Flood | DDoS `packet_in` flood |
| **exp03** | LOFT attack | Low-rate OpenFlow trust probes |
| **exp04** | Rush Hour | Legitimate surge — no persistent block |
| **exp05** | DRL / Rollback | Cooldown rollback + DRL action stub |

## Run

```bash
# Needs controller up: python -m api.app --port 8080
python scripts/run_experiment.py --exp exp02_ddos
python scripts/run_experiment.py --exp exp05_drl   # also trains DRL agent

# Ablation (architectures × k·σ) — offline, no controller required
python scripts/run_sweep.py --epochs 3 --samples 800
```

Each experiment writes `experiments/<id>/results/report.md` + `metrics.json`.
Ablation writes `results/ablation/ablation_report.md`.

Configs are YAML-driven, for example:

```yaml
attack:
  type: ddos
  duration: 120
  packet_rate: 5000
```
