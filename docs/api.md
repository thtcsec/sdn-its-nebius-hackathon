# REST API

Base URL: `http://127.0.0.1:8080`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Evidence ops console |
| GET | `/api/v1/status` | Health, stats, τ, `lab_mode`, `scorer_mode`, OF backend |
| GET/POST | `/api/v1/settings` | Runtime settings (Lab mode, theme, cooldowns, …) |
| GET | `/api/v1/lab` | OpenFlow/agent snapshot + mitigation log |
| GET | `/api/v1/empirical` | Cached InSDN / CIC metrics from `results/` |
| GET | `/api/v1/active_rules` | Active mitigation rules |
| GET | `/api/v1/rollback_history` | Revoked rules history |
| POST | `/api/v1/anomaly_alert` | Policy Detect/Contain/Rollback |
| GET/POST | `/api/v1/infer` | Score window — see honesty fields below |
| GET | `/api/v1/telemetry` | Live score tick for RE chart |
| GET/POST | `/api/v1/replay` | List / load replay scripts |
| POST | `/api/v1/replay/step` | One replay step |
| GET | `/api/v1/latency_cdf` | Latency percentiles |
| GET | `/api/v1/topology` | Topology stub (lab hook) |
| GET/POST | `/api/v1/export/report` | Preview (GET) / write+download metadata (POST) |
| GET | `/api/v1/export/report/file?path=` | Download file under `results/` |
| POST | `/api/v1/export/onnx` | Export ONNX / TorchScript |

## Infer honesty fields

```json
{
  "mode": "MODEL",
  "source": "model",
  "simulated": false,
  "ground_truth": "DDoS_PacketIn_Flood",
  "prediction": "LOFT_LowRate_Attack",
  "predicted_label": "LOFT_LowRate_Attack",
  "correct": false,
  "scenario_override": false,
  "preprocess_mode": "fitted_standard_scaler",
  "banner": null
}
```

| `mode` | Meaning |
|--------|---------|
| `MODEL` | Checkpoint loaded; prediction from weights |
| `SIMULATION` | Demo fallback only (Lab mode refuses this) |
| `DEGRADED` | No checkpoint; `inference_disabled: true`, scores null |

Lab mode (`runtime.lab_mode` / Settings): `scenario_override=false`, no simulation fallback.

## Anomaly alert payload

```json
{
  "alert_id": "ALT-9823",
  "dpid": "0000000000000001",
  "src_ip": "10.0.0.15",
  "attack_type": "DDoS_PacketIn_Flood",
  "reconstruction_error": 1.482,
  "confidence": 0.985,
  "cooldown_seconds": 30
}
```

Supported `attack_type`: `DDoS_PacketIn_Flood`, `LOFT_LowRate_Attack`, `RSU_Link_Fault`, `RushHour_Burst`.

Implementation: `api/routes.py`, `sdn_its.controller.rest_api`, `sdn_its.ai.live_scorer`.
