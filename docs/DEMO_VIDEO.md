# Demo video script (&lt; 3 minutes)

Status: **script ready — recording not yet uploaded**.

## Suggested shot list (≈150–170s)

1. **0:00–0:20** — Title: SDN-ITS × Nebius × NVIDIA SOLO; open console `127.0.0.1:8080`; note mock OF + DEGRADED classifier OK for judge path.
2. **0:20–0:50** — Hackathon board: run fixture `01_legitimate_rush_hour` offline → preserve/observe; show synthetic camera metadata (no RTSP).
3. **0:50–1:20** — Fixture `02_suspicious_loft_stable_camera` → rule rate_limit; Nemotron rationale; demo gate note.
4. **1:20–1:50** — Fixture `07_unsafe_escalation_blocked` → model wants `temporary_drop`, gate forces `protect_safety` / observe; highlight audit.
5. **1:50–2:20** — Terminal: `python scripts/run_hackathon_benchmark.py --mode offline --allow-containment-in-demo`; show summary rates + honesty_note.
6. **2:20–2:50** — Optional: `verify_nebius_nemotron.py` with `evidence_class: real_api` (blur any env UI); model id Nano.
7. **2:50–3:00** — Limitations slide: mock OF, synthetic camera, no claimed accuracy win without numbers.

Upload URL placeholder: _TBD — add YouTube link here when published._
