# Hackathon incident fixtures

Synthetic, public fixtures for judge-ready cyber–physical investigation demos.

Each JSON file contains:

- `network_prediction` — detector/label hypothesis (not live TCN-GRU)
- `telemetry` — SDN/RSU counters (synthetic)
- `camera` — **same-zone physical context metadata** (synthetic; no RTSP URLs)
- `expected` — honest scoring targets for the benchmark
- optional `synthetic_model_output` — offline Nemotron-path stand-in (clearly labeled)

No private camera inventories or research checkpoints required.
