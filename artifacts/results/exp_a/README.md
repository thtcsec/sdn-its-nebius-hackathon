# Experiment A artifacts

Run (WSL root):

```bash
sudo bash scripts/run_exp_a_lab.sh
# or from Windows:
# .\scripts\run_exp_a.ps1
```

Produces `exp_a_metrics.json` here and under `experiments/exp02_ddos/results/`.

Until a live run succeeds, `.\scripts\run_exp_a.ps1 -DryRun` writes a schema-only file with `network_evidence: false`.
