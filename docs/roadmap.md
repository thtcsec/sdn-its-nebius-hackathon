# Roadmap

## Done
- [x] Research framework layout (`src/sdn_its`, `api`, `experiments`, `configs`)
- [x] Detect → Contain → Rollback mitigation modules
- [x] Flask REST API + Command Center dashboard
- [x] Synthetic + InSDN telemetry pipelines (HF download / prepare)
- [x] Full InSDN windows NPZ wired into train / evaluate / compare (not just 800-row sample)
- [x] Temporal Transformer ablation baseline alongside TCN-GRU
- [x] Eval exports: confusion matrix PNG + `eval_metrics.json`
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
- [ ] Real Ryu OpenFlow 1.3 app on Mininet-WiFi (adapter + checklist ready)
- [ ] Paper-ready multi-seed sweeps → IEEE/Q1 draft tables
- [ ] Cross-dataset holdout (InSDN train → CIC-IDS2017 test) once CIC is downloaded
- [ ] Full SUMO / Mininet-WiFi mobility coupling
- [ ] Production webhook integrations (Slack/Teams templates)
