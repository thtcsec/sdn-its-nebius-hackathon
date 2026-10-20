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
| Schema validation + safety gates (incl. evidence sufficiency) | `schema.py`, `safety.py` |
| Single-shot + multi-step investigation agent | `agent.py`, `multi_step.py`, `evidence_tools.py` |
| Public synthetic incident fixtures + demo scenarios | `datasets/hackathon/incidents/`, `scenarios/` |
| Held-out oracle eval + fair ablation A/B/C/D | `scripts/run_heldout_eval.py`, `run_ablation_study.py` |
| Judge / multi-step demo scripts | `scripts/run_judge_demo.py`, `run_multistep_demo.py` |
| API: incidents / run / multistep / audit | `api/routes.py` (`/api/v1/hackathon/*`) |
| JunctionTrace product UI at `/` (research at `/research`) | `dashboard/templates/junctiontrace.html`, `static/junctiontrace.*` |
| Hosted guards: token, rate, concurrency, daily budget, demo policy | `hackathon_guard.py`, `security.py`, middleware |
| Console investigation board + traces | `dashboard/templates/index.html` (research) |
| Evidence / audit docs | `HACKATHON_AUDIT.md`, `docs/JUDGE_DEMO.md`, `COMPETITION_DELTA_REPORT.md`, `artifacts/hackathon/` |

## Honesty constraints

- Demo mode blocks containment intentions by default (mock OF).
- Offline benchmark uses **labeled synthetic** / deterministic planner paths — **not** live Nebius; offline ~92% ≠ Nemotron accuracy.
- Camera context in the judge path is **synthetic metadata**; OpenFlow is **mock**.
- Blind live Nemotron sample is small (n=4 in `blind_redteam_eval.json`); matched and blind studies stay separate.
- Paired gate C→D did not show an accuracy win on the matched live sample; adversarial synthetics prove enforcement.
- No fabricated accuracy gains: read `summary.honesty_note` in benchmark JSON.
- Submission blockers / tip SHA / CI: `CURRENT_SUBMISSION_STATUS.md`.
