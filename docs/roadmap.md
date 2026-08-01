# Roadmap

## Done
- [x] Research framework layout (`src/sdn_its`, `api`, `experiments`, `configs`)
- [x] Detect → Contain → Rollback mitigation modules
- [x] Flask REST API + Command Center dashboard
- [x] Synthetic + InSDN telemetry pipelines (HF download / prepare)
- [x] Full InSDN windows NPZ wired into train / evaluate / compare (not just 800-row sample)
- [x] Temporal Transformer ablation baseline alongside TCN-GRU
- [x] Eval exports: confusion matrix PNG + `eval_metrics.json`
- [x] CIC-IDS2017 HF download mirror + prepare → `cic_windows.npz`
- [x] Cross-dataset holdout script (InSDN train scaler → CIC test)
- [x] OpenFlow backends: `mock` | `queue` | `ryu` + Ryu app + lab checklist
- [x] Live TCN-GRU inference API (`/api/v1/infer`, `/telemetry`) + online τ
- [x] Settings GET/POST, theme / role / dataset / webhook
- [x] Scenario replay timeline + before/after compare mode
- [x] Feature attribution (per-feature RE)
- [x] Experiment runner with metrics + Markdown reports
- [x] Ablation sweep (architectures × k·σ) + latency CDF benchmarks
- [x] ONNX / TorchScript export helpers
- [x] DRL replay-buffer + target-network training loop (exp05)
- [x] Console report / ONNX export endpoints

## Lab / paper (needs Linux or longer runs)
- [ ] Sign off WSL2 Mininet+Ryu lab against `docs/lab_checklist.md` pass criteria
- [ ] Paper-ready multi-seed sweeps → IEEE/Q1 draft tables
- [ ] Full SUMO / Mininet-WiFi mobility coupling
- [ ] Production webhook integrations (Slack/Teams templates)
