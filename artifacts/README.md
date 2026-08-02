# Artifacts

Paper-facing evidence mirrors (metrics JSON / confusion matrices).

- `models/model_card.json` — checkpoint metadata (weights may be local-only)
- `results/exp_insdn/` — InSDN in-domain eval
- `results/cross_dataset/` — CIC zero-shot / adapted
- `results/ablation/` — architecture sweep outputs if present

Rebuild mirrors: `.\scripts\sync_artifacts.ps1`
Reproduce tables: `.\reproduce.ps1`
