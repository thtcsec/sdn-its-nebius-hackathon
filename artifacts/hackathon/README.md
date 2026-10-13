# Hackathon evidence (Nebius × NVIDIA)

Non-secret runtime evidence from verification / evaluation scripts:

| File | Produced by | Notes |
|------|-------------|--------|
| `nebius_verify_last.json` | `scripts/verify_nebius_nemotron.py` | gitignored pattern `*_last.json`; `real_api` when live key works |
| `real_api_evidence_redacted.json` | curated bundle | Redacted successful Token Factory calls |
| `multistep_demo_traces.json` | `scripts/run_multistep_demo.py` | ≥4 scenario traces (offline planner + real tools) |
| `ablation_offline.json` | `scripts/run_ablation_study.py --skip-real --allow-containment-in-demo` | Fair A/B/C/D on held-out (planner ≠ live Nemotron) |
| `ablation_with_real.json` | budgeted live run | Mixed evidence classes; see summary |
| `ablation_real_summary.json` | redacted rollup | real_api-only n + cost |
| `heldout_eval_*.json` | `run_heldout_eval.py` | Prior oracle eval snapshots |
| `secret_license_scan.json` | `scan_secrets_and_license.py` | Hygiene |

Do not commit API keys. Offline planner / synthetic fixtures must never be labeled as live NVIDIA decisions.
