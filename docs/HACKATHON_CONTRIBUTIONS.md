# Hackathon contributions vs prior research

## Prior research baseline (inherited)

- TCN-GRU / temporal models, InSDN-oriented train/eval
- Detect → temporary contain → rollback PolicyEngine
- Rule-based camera fusion (`FusionEngine`)
- Flask evidence console, mock OpenFlow default
- IEDE academic packaging under the research repository

**Research source of truth (do not mix edits):** `D:\tu_projects\sdn-its-resilience-ai`

## Substantial new hackathon work (this repo)

| Area | Location |
|------|----------|
| Nebius Token Factory client + `.env` loader | `src/sdn_its/llm/`, `src/sdn_its/utils/env.py` |
| Schema validation + safety gates | `schema.py`, `safety.py` |
| Cyber–physical investigation agent | `src/sdn_its/llm/agent.py` |
| Public synthetic incident fixtures | `datasets/hackathon/incidents/` |
| Rule vs Nemotron benchmark | `scripts/run_hackathon_benchmark.py` |
| Judge demo script | `scripts/run_judge_demo.py` |
| API: incidents / run / audit | `api/routes.py` (`/api/v1/hackathon/*`) |
| Console investigation board | `dashboard/templates/index.html` |
| Evidence / audit docs | `HACKATHON_AUDIT.md`, `docs/JUDGE_DEMO.md`, `artifacts/hackathon/` |

## Honesty constraints

- Demo mode blocks containment intentions by default (mock OF).
- Offline benchmark uses **labeled synthetic** model JSON — not claimed as live Nebius.
- No fabricated accuracy gains: read `summary.honesty_note` in benchmark JSON.
