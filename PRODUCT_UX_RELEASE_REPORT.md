# PRODUCT UX RELEASE REPORT — JunctionTrace

**Branch:** `hackathon/nebius-nvidia`  
**Base verified:** `bf358a882623036750cc20cd7e887aa9dca8ad3a`  
**Release tip:** `1770415d46c1d2876a3ed3df9e01a1b380222e80`  

## Naming

Provisional name **CrossSignal AI** was **not** used: ARIN lists **CrossSignal, LLC**.  
Product identity shipped: **JunctionTrace — Incident Investigator**.

## What changed (frontend architecture)

| Route | Template | Role |
|-------|----------|------|
| `/` | `dashboard/templates/junctiontrace.html` | **New** hackathon product |
| `/research` | `dashboard/templates/index.html` | Preserved research / IEDE lab console |

Assets:

- `dashboard/static/junctiontrace.css` — navy / teal product system  
- `dashboard/static/junctiontrace.js` — scenario board, 7-step journey, offline/real modes  
- `GET /api/v1/hackathon/capabilities` — non-secret Nebius readiness (never returns the key)

Backend investigation APIs reused unchanged in contract:

- `GET /api/v1/hackathon/incidents`
- `POST /api/v1/hackathon/multistep`
- `GET /api/v1/hackathon/audit`

## Judge-first journey

First viewport (1440×900): product identity, Nemotron/Nebius disclosure, problem statement, Investigate CTA, four scenarios, “what’s different” card.  
No Tsinghua IEDE branding, RE charts, tau stats, topology, or lab settings on `/`.

Investigation steps 1–7 animate from the real multistep trace (tools, retrieves, conclude source, gate PASS/OVERRIDE, rule-only comparison).

## Scenarios

| Card | ID | Intent |
|------|-----|--------|
| A | `scenario_rush_vs_attack` | Legitimate congestion |
| B | `scenario_loft_stable` | Credible attack / quiet physical |
| C | `scenario_missing_camera` | Missing / stale evidence |
| D | `scenario_conflict_signals` | Contradictory signals (new scenario wrapper for demo) |

## E2E + screenshots

Script: `scripts/e2e_product_ui.py`  
Report: `artifacts/hackathon/e2e_product_report.json` (**11/11 PASS**)

Screenshots in `artifacts/hackathon/product_screens/`:

1. `01_landing_1440x900.png` — fresh product landing  
2. `02_investigating_1440x900.png` — in-progress loading  
3. `03_complete_offline_1440x900.png` — deterministic planner labeled offline  
4. `04_complete_real_1440x900.png` — LIVE Nebius / `nemotron_conclude`  
5. `05_research_1440x900.png` — `/research` preserved IEDE console  
6. `06_mobile_390x844.png` — mobile CTA usable  

Visual QA: landing and investigation boards inspected; mobile header chips compacted after first capture.

## Demo walkthrough (&lt;3 min script)

1. Open `/` — state hero + Nebius/Nemotron chips + mock OF.  
2. Select **C Missing / stale evidence** → **Safe offline** → Investigate — show tools + observe vs rule-only `rate_limit`.  
3. Select **B Quiet zone + low-rate anomaly** → **Real Nebius** → Investigate — show full trace (`LIVE Nebius / real_api` when credentials exist); do not overclaim a certain cyberattack — model may observe while rule-only rate-limits.  
4. Optional: open `/research` once to show preserved lab (not the product).  
5. Close: OpenFlow remains mock; camera synthetic; gate authoritative.

## Pre-existing vs new (disclosure)

**Pre-existing (research lineage):** Flask controller, FusionEngine, PolicyEngine, mock OF, camera store, IEDE console (`index.html`), detection/RE lab surfaces under `/research`.

**New for Nebius × NVIDIA hackathon product:** JunctionTrace UI, route split, capabilities endpoint, multistep investigation agent/tools/gates (prior commits), scenario D wrapper, product E2E + screenshots.

## CI

Workflow: `.github/workflows/hackathon-light.yml` (includes `tests/test_product_ui.py`).  
**CI URL:** https://github.com/thtcsec/sdn-its-nebius-hackathon/actions/runs/38771544924 — **success**

## Remaining blockers (owner approval)

1. Repository still **private**  
2. No public YouTube recording of this product journey  
3. No hosted demo URL deployed  
4. Devpost submit not authorized  

No visibility flip, paid deploy, or Devpost submit performed.
