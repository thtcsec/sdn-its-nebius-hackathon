# Evidence console & research posture

Framing: this repo is a **reversible mitigation testbed**, not a live SOC. UI KPIs mean:

| Label | Meaning |
|-------|---------|
| Policy decisions | Alerts processed by the policy engine |
| Pending / in-memory rules | FlowRule objects in controller memory |
| Rush-hour preserved (policy) | Policy mapped `RushHour_Burst` → ignore (not counterfactual FP) |
| Policy p50/p95 | In-process policy timing — **not** switch install / E2E |
| OpenFlow rules installed | Incremented only when OF backend has network evidence |

Event chain (when streamer uses `/api/v1/infer`):  
`window_id → inference_id → policy_decision_id → flow_mod_ids → switch_ack`

## Status strip (ops UI)

The dashboard evidence bar shows:

1. **MODEL** — `LOADED` / `SIMULATION` / `DEGRADED`
2. **OF** — backend name (`mock` / `http` / …) and agent connectivity
3. **NET** — `EVIDENCE` only if backend ≠ mock **and** agent connected; else `NO EVIDENCE`
4. **PREPROCESS** — fitted scaler vs demo per-window z-score mismatch
5. **GT / PRED / MATCH** — ground truth vs model prediction after inject/replay
6. **INFER** — controller `/api/v1/infer` call count (streamer must hit this path)

If the red banner or **NET · NO EVIDENCE** is visible, **do not** treat Active/Pending rules or latency as network outcomes.

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

## Camera fusion (not a video wall)

**Honest boundary:** live RTSP currently feeds a **visual activity proxy** (edge energy),
not a vehicle detector. Provenance fields:

- `visual_activity` / `activity_band` / `is_vehicle_count: false` for RTSP proxy
- `vehicle_count` / `queue_length_m` only when `is_vehicle_count: true` (synthetic Exp B/C or future detector)
- Stream quality: `stream_available` · `frame_fresh` · `scene_valid` · `analytics_valid`
- Preview: `GET /api/v1/camera/<id>/preview` (one overwritten JPEG, no archive)

Fusion is **rule-based** and explainable (`reason_codes`). Thresholds are handcrafted;
see `scripts/exp_bc_sensitivity.py` → `artifacts/results/exp_bc/exp_bc_sensitivity.json`.

- `GET /api/v1/camera` — cards + aggregate
- `POST /api/v1/camera/scenario` — synthetic rush / stable / mixed
- `scripts/exp_bc_camera_fusion.py` → `artifacts/results/exp_bc/exp_bc_fusion.json`

`pass: true` on Exp B/C proves **rule correctness on scripted inputs**, not live-camera FP reduction.
`false_positives_avoided` increments only when fusion **corrects** an anomaly prediction using camera context.

Camera → fusion → **OpenFlow + traffic outcome** still belongs to Exp A-style evidence; fusion alone is policy intelligence on paper until OF is verified.

Privacy (prototype): inventory RTSP URLs gitignored; no raw URL logs; single overwritten frame; no video archive. Production needs secret store, ACL, TLS/private net, retention, audit.

## Experiment A metrics file

After `.\scripts\run_exp_a.ps1` (WSL):

- `experiments/exp02_ddos/results/exp_a_metrics.json`
- `artifacts/results/exp_a/exp_a_metrics.json`

Expect `network_evidence: true`, three arms, and `temporary.rollback_success`.  
ICMP delivery ratios are **data-plane proxies** — not controller PacketIn/s (needs Ryu).

Console board: `GET /api/v1/lab/evidence` → Traffic / Detection / Actuation / Outcome.

## Minimum evidence for a reviewer

- [ ] `model_card.json` present
- [ ] InSDN `metrics.json` + confusion matrix
- [ ] Cross-dataset adapted metrics (if claiming generalization)
- [ ] Console screenshot with **MODEL · LOADED** and **Lab** badge
- [ ] **Exp A** `exp_a_metrics.json` with `network_evidence: true` (or honest dry-run)
- [ ] Optional: `ovs-ofctl dump-flows` under lab run notes
- [ ] Optional: `reproduce.ps1` log + `run_manifest.json`
