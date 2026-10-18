# Devpost submission package — JunctionTrace

**Track:** Best Apps and Agents  
**Status:** Ready to paste. Do **not** submit without owner approval.  
**Re-confirm official Nebius × NVIDIA hackathon rules immediately before release.**

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

**JunctionTrace** is a standalone hackathon product UI (`/`) that:

1. Presents four operator scenarios (legitimate congestion, quiet-zone anomaly, missing/stale evidence, contradictory signals).
2. Runs **Safe offline** (deterministic planner + real tool logic) or **Real Nebius** (live NVIDIA Nemotron via Token Factory).
3. Shows a multi-step investigation timeline: incident → uncertainties → tool selection → retrieved evidence → recommendation → **policy gate** → operator outcome.
4. Compares **rule-only baseline** vs investigation + gate side-by-side.
5. Keeps OpenFlow **mock**, camera fields as **synthetic metadata**, and demo mode containment-safe on hosted deployments.
6. Preserves the pre-existing research lab console at `/research`.

Hosted demos enforce a strong API token, daily application spend quota, rate/concurrency limits, and disable legacy model routes.

---

## Technology and architecture

- **Frontend:** JunctionTrace product page (HTML/CSS/JS) — DOM-safe rendering (`textContent` only for untrusted fields).
- **API:** Flask `api.app` — `/api/v1/hackathon/multistep` (product), audit, capabilities; research routes retained.
- **Agent:** Multi-step tool loop (`retrieve_network_telemetry`, `inspect_camera_metadata`, `check_physical_evidence_quality`, `compare_temporal_windows`, `identify_contradictions`, …) → conclude → deterministic safety gate.
- **Model path:** Nebius Token Factory OpenAI-compatible chat completions → `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`.
- **Safety:** Schema validation / repair, evidence-sufficiency gate, hosted fail-closed config, SQLite-backed application quota with crash-conservative accounting.
- **Actuation:** Mock OpenFlow only in judge path (no live switch containment).

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

- Offline / planner accuracy must **not** be advertised as Nemotron accuracy.
- Held-out and ablation studies show the deterministic planner is often competitive; Nemotron value is **tool-mediated investigation**, labeled live conclude, and operator-trace transparency — not a blanket accuracy win on every synthetic case.
- Camera inputs in the judge path are **synthetic metadata**, not live RTSP.
- OpenFlow is **mock** — advisory demo, not production ITS deployment.
- Application daily budget is **not** a Nebius provider hard spending cap.
- Model outcomes vary; Scenario B may `observe` while rule-only `rate_limit` — the full trace is the product.

Artifacts: `artifacts/hackathon/`, `COMPETITION_DELTA_REPORT.md`, `JUDGE_ACCEPTANCE_REPORT.md`.

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
- Demo video: _TBD after owner-approved YouTube upload_  

---

## Track confirmation

**Best Apps and Agents** — agentic multi-step investigation product using NVIDIA Nemotron on Nebius Token Factory with a real operator-facing UI and safety gate.
