# Evidence console & research posture

## Status strip (ops UI)

The dashboard evidence bar shows:

1. **MODEL** — `LOADED` / `SIMULATION` / `DEGRADED`
2. **OF** — backend name (`mock` / `http` / …) and agent connectivity
3. **PREPROCESS** — fitted scaler vs demo per-window z-score mismatch
4. **GT / PRED / MATCH** — ground truth vs model prediction after inject/replay

If the red banner is visible, **do not screenshot numbers as paper results**.

## Default runtime (research-first)

Controller defaults:

- `lab_mode: true`
- `scenario_override: false`
- `ambient_re: false`
- `theme: research`

Demo injects that force attack labels require turning **Lab mode off** and enabling
**Scenario label override** in Settings. That path is explicitly marked `OVERRIDDEN (DEMO)`.

## Artifact layout

```text
artifacts/
├── README.md
├── models/
│   └── model_card.json
└── results/
    ├── exp_insdn/          # InSDN in-domain
    ├── cross_dataset/      # CIC zero-shot + adapted
    └── ablation/           # architecture × kσ JSON
```

Refresh with `scripts/sync_artifacts.ps1` after any eval run.

## Minimum evidence for a reviewer

- [ ] `model_card.json` present
- [ ] InSDN `metrics.json` + confusion matrix
- [ ] Cross-dataset adapted metrics (if claiming generalization)
- [ ] Console screenshot with **MODEL · LOADED** and **Lab** badge
- [ ] Optional: `ovs-ofctl dump-flows` under lab run notes
- [ ] Optional: `reproduce.ps1` log + `run_manifest.json`
