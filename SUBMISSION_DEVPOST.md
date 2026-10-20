# Devpost submission package — JunctionTrace

**Track:** Best Apps and Agents  
**Paste readiness:** Draft text below is ready to paste into Devpost fields.  
**Competition status:** **BLOCKED** until owner completes public repo + visible license, working demo URL, public YouTube &lt;3 min, feedback form, and final Devpost submit.  
**Authority:** `SUBMISSION_READY.md`.  
**Rules:** https://nebiusglobalaihackathon.devpost.com/rules — re-confirm immediately before release.

---

## Project name

**JunctionTrace**

## Tagline

A traffic surge is not always an attack — investigate physical context before you contain.

---

## Problem and target audience

Intelligent Transportation System (ITS) and SOC operators often receive network anomaly labels that look like DDoS or low-rate attacks. Jumping straight to containment can disrupt legitimate mobility traffic (rush-hour queues, event surges). The operator pain point: **decide whether a surge is congestion, evidence gaps, or a credible cyber anomaly — without live video pipelines or unsafe switch pushes in a demo.**

**Audience:** SOC / ITS analysts, cyber-physical security researchers, and hackathon judges evaluating agentic use of NVIDIA Nemotron on Nebius Token Factory.

---

## What it does (product functionality)

**Operator problem:** Network anomaly labels can look like DDoS. Immediate containment can harm legitimate mobility (rush hour, events). Operators need evidence-backed investigation before disruptive action.

**JunctionTrace** is a standalone hackathon product UI (`/`) that:

1. Presents four operator scenarios (legitimate congestion, quiet-zone anomaly, missing/stale evidence, contradictory signals).
2. Runs **Safe offline** (deterministic planner + real tool logic) or **Real Nebius** (live NVIDIA Nemotron via Token Factory).
3. Runs a **multi-step tool-selection loop**: incident → uncertainties → model chooses evidence tools → tools return telemetry / synthetic camera metadata / quality checks → model conclude → **deterministic policy gate** (authoritative) → operator outcome.
4. Compares **rule-only baseline** vs investigation + gate side-by-side.
5. Keeps OpenFlow **mock** (does **not** control a real traffic switch), camera fields as **synthetic metadata**, and demo mode containment-safe on hosted deployments.
6. Preserves the pre-existing research lab console at `/research`.

**Physical-context example:** A quiet-zone or LOFT-like surge may look like an attack on network features alone; inspecting same-zone synthetic camera metadata / contradictions can change the recommendation (e.g. soft containment vs observe/preserve) — see matched traces in `WINNING_EVIDENCE.md` and product Scenario B.

**Roles:** Nemotron = tool-mediated investigation + labeled `real_api` conclude. Deterministic gate / offline planner = policy and fail-closed controls. Hosted demos add token auth, application spend quota, rate/concurrency limits.

---

## Technology and architecture

- **Frontend:** JunctionTrace product page (HTML/CSS/JS) — DOM-safe rendering (`textContent` only for untrusted fields).
- **API:** Flask `api.app` — `/api/v1/hackathon/multistep` (product), audit, capabilities; research routes retained.
- **Agent:** Multi-step tool loop (`retrieve_network_telemetry`, `inspect_camera_metadata`, `check_physical_evidence_quality`, `compare_temporal_windows`, `identify_contradictions`, …) → conclude → deterministic safety gate.
- **Model path:** Nebius Token Factory OpenAI-compatible chat completions → `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`.
- **Safety:** Schema validation / repair, evidence-sufficiency gate, hosted fail-closed config, SQLite-backed application quota with crash-conservative accounting.
- **Actuation:** Mock OpenFlow only in the judge path. The demo does **not** install flows on a real traffic switch. Recommendations are advisory.

---

## NVIDIA / Nebius integration

| Component | Role |
|-----------|------|
| **Nebius Token Factory** | Hosted inference API + API keys (server-side only) |
| **NVIDIA Nemotron 3 Nano 30B-A3B** | Tool selection + conclude turns for real-mode investigations |
| **Evidence** | `evidence_class=real_api` labeled distinctly from offline planner |

Credentials never leave the server; the browser only receives capability flags and investigation summaries.

---

## Evidence and benchmark limitations (honest)

- **OpenFlow is mock** in the competition demo; recommendations are advisory.
- **Camera fields are synthetic metadata**, not a live production camera / RTSP pipeline.
- Offline ablation arm D ≈ **92%** (`ablation_offline.json`, n=25, deterministic planner) must **never** be presented as Nemotron accuracy.
- **Matched live** Nemotron studies (small curated set) and the **blind** study are separate; do not merge rates.
- Blind live Nemotron arm C (`blind_redteam_eval.json`): **n=4**, **3/4** vs assumption-labeled oracle, mean latency **~17.2 s**, fallback rate **0.25**, `of_backend=mock`, `camera_label=synthetic_metadata_only`. This does **not** establish real-world ITS incident accuracy.
- Paired gate study: **no accuracy improvement attributable to the gate** on the matched live C→D sample; adversarial synthetic tests show policy enforcement separately.
- Some live runs use **deterministic_fallback**; latency is seconds-scale advisory investigation, not real-time control-loop latency.
- Application daily budget is **not** a Nebius provider hard spending cap.
- Model outcomes vary; Scenario B may `observe` while rule-only `rate_limit` — the full trace is the product.

Artifacts: `artifacts/hackathon/`, `CURRENT_SUBMISSION_STATUS.md`, `JUDGE_ACCEPTANCE_REPORT.md` (historical SHA `dcc7ac0`), `WINNING_EVIDENCE.md`, `FINAL_RELEASE_GATE.md`.

---

## Prior research vs new hackathon work

**Inherited research baseline:** TCN-GRU / SDN-ITS detect→contain→rollback stack, FusionEngine, IEDE research console (now at `/research`). Source of truth for pure research: separate resilience-ai repo.

**New in this hackathon repo:** Nebius client, multi-step Nemotron investigator, safety/schema gates, JunctionTrace product UI, hosted security/quota guards, judge scenarios, ablation/held-out tooling, and submission evidence.

Details: `docs/HACKATHON_CONTRIBUTIONS.md`.

---

## Deployment and testing instructions

**Local (loopback):**

```bash
export PYTHONPATH=src:.
# optional NEBIUS_API_KEY in .env for Real mode
python -m api.app --host 127.0.0.1 --port 8080
# open http://127.0.0.1:8080/
pytest -q tests/test_hackathon_security.py tests/test_product_ui.py
python scripts/e2e_product_ui.py   # Playwright; real_api SKIPPED without key
```

**Hosted judge package (owner approval required):** see `docs/JUDGE_HOSTING.md` and `deploy/judge/`.

```bash
cp deploy/judge/.env.example deploy/judge/.env   # fill secrets
cd deploy/judge && docker compose up -d --build
```

---

## Feedback on Nebius Token Factory and NVIDIA Nemotron

(Use / extend `docs/NEBIUS_NVIDIA_FEEDBACK.md`)

**Worked:** OpenAI-compatible Token Factory API; Nemotron Nano followed bounded tool-call/conclude loops well enough for a cost-capped demo; model listing helped confirm availability; Nano cost/latency fit iterative investigation.

**Friction:** Reasoning-heavy variants can burn tokens and return unparseable JSON; JSON-mode support varies by SKU; pricing endpoints for honest cost estimates would help.

**Suggestion:** Ship an “agent loop” cookbook (tool_call → tool result → conclude) with recommended max_tokens and repair guidance for Nano vs larger Nemotron SKUs.

---

## Built with

Python, Flask, Nebius Token Factory, NVIDIA Nemotron, Playwright, Docker, Caddy, SQLite

---

## Try it out

- Local: instructions above  
- Hosted URL: _TBD after owner-approved deploy_  
- Demo video: local canonical file `junctiontrace_REAL_APP_DEMO.mp4` (75.6 s real-app recording) — YouTube URL _TBD after owner-approved upload_  

---

## Track confirmation

**Best Apps and Agents** — agentic multi-step investigation product using NVIDIA Nemotron on Nebius Token Factory with a real operator-facing UI and safety gate.
