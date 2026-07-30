# REST API

Base URL (demo): `http://127.0.0.1:8080`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Command Center dashboard |
| GET | `/api/v1/status` | Controller health + stats + live τ |
| GET/POST | `/api/v1/settings` | YAML defaults + runtime console settings |
| GET | `/api/v1/active_rules` | Active mitigation rules |
| GET | `/api/v1/rollback_history` | Revoked rules history |
| POST | `/api/v1/anomaly_alert` | AI alert → Detect/Contain/Rollback |
| GET/POST | `/api/v1/infer` | Live TCN-GRU score (+ optional auto-alert) |
| GET | `/api/v1/telemetry` | Ambient live score for RE chart |
| GET/POST | `/api/v1/replay` | List / load scenario replay scripts |
| POST | `/api/v1/replay/step` | Execute one replay step |
| GET | `/api/v1/latency_cdf` | Policy/infer latency percentiles |
| GET | `/api/v1/topology` | Mock OVS/RSU health (lab hook) |
| POST | `/api/v1/export/report` | Write Markdown snapshot under `results/` |
| POST | `/api/v1/export/onnx` | Export ONNX / TorchScript |

## Anomaly alert payload

```json
{
  "alert_id": "ALT-9823",
  "dpid": "0000000000000001",
  "src_ip": "10.0.0.15",
  "dst_ip": "10.0.0.1",
  "attack_type": "DDoS_PacketIn_Flood",
  "reconstruction_error": 1.482,
  "confidence": 0.985,
  "cooldown_seconds": 30
}
```

Supported `attack_type` values: `DDoS_PacketIn_Flood`, `LOFT_LowRate_Attack`, `RSU_Link_Fault`, `RushHour_Burst`.

## Infer payload

```json
{ "scenario": "ddos", "adapt_tau": false, "auto_alert": false }
```

`scenario`: `normal` | `ddos` | `loft` | `rush_hour`

Implementation: `api/routes.py`, `api/schemas.py`, `sdn_its.controller.rest_api`, `sdn_its.ai.live_scorer`.
