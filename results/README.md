# Results

Paper-oriented evaluation outputs. Canonical mirrors for reviewers also live in
[`../artifacts/results/`](../artifacts/results/).

| Path | Content |
|------|---------|
| `tcn_gru/` | InSDN eval metrics + confusion matrix |
| `transformer/` | Transformer ablation eval |
| `cross_dataset/` | CIC zero-shot / adapted |
| `ablation/` | Architecture × kσ sweep JSON/MD |
| `console/` | **Ephemeral** console exports (gitignored) |

Refresh artifacts after eval:

```powershell
.\scripts\sync_artifacts.ps1
```
