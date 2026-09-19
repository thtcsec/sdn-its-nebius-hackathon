# Roadmap

## Done (research artifact posture)

- [x] Research framework layout (`src/sdn_its`, `api`, `experiments`, `configs`)
- [x] Detect → Contain → Rollback mitigation modules
- [x] Flask REST API + evidence-oriented ops console
- [x] **Lab mode default** — no scenario label cheat; no silent fake scores
- [x] Explicit `MODEL` / `SIMULATION` / `DEGRADED` + GT vs prediction in API/UI
- [x] `artifacts/` + `datasets/manifests/` + `reproduce.ps1` + lean `package.ps1`
- [x] InSDN / CIC prepare, train, evaluate, cross-dataset adaptation
- [x] Temporal Transformer ablation baseline
- [x] Eval exports: confusion matrix PNG + `eval_metrics.json` (tracked under `results/` + `artifacts/`)
- [x] OpenFlow backends: `mock` | `queue` | `http/wsl` | `ryu` + WSL of_agent
- [x] Live infer, replay, attribution, report preview/download
- [x] Checkpoint bundles scaler mean/scale when retrained
- [x] Docs: [REPRODUCE](REPRODUCE.md), [EVIDENCE](EVIDENCE.md), honest README
- [x] Split-before-window protocol (`rows_before_window_v1`) + methodology docs (CIC-IDS2017 naming, binary metric defs)
- [x] Lab console hardening: loopback bind default, security headers, optional `SDN_API_TOKEN`, webhook SSRF guard, of_agent token + payload cap

## Next (credibility over cosmetics)

- [ ] One complete Mininet evidence pack: PCAP + `ovs-ofctl` before/after + recovery times
- [ ] Multi-seed paper tables + `predictions.csv` + `run_manifest.json` per seed
- [ ] Harder overlapping scenarios (rush-hour ≈ mild DDoS, LOFT mixed, concept drift)
- [ ] Ablation table (GRU/LSTM/TCN/TCN-GRU/Transformer × kσ) fully regenerated into `artifacts/`
- [ ] Resilience metrics: false-block rate, PacketIn reduction, legitimate delivery, recovery time
- [ ] Live preprocess always uses fitted scaler (retrain all published checkpoints with scaler fields)
- [ ] SUMO / Mininet-WiFi mobility coupling
- [ ] Topology discovery from controller (not hard-coded SVG only)
