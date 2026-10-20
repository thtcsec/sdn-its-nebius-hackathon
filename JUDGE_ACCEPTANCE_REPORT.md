# JUDGE ACCEPTANCE REPORT — Independent Red-Team

> **HISTORICAL AUDIT — do not treat as tip status.**  
> Examined HEAD: `dcc7ac0f1f896df5308800b796cb05b60517dd71` (2026-10-13).  
> Blind JSON and technical findings below remain valid evidence for that snapshot.  
> **Current tip / CI / video / submission blockers:** see `CURRENT_SUBMISSION_STATUS.md` (tip `d85fb6f`, tip CI [39258073978](https://github.com/thtcsec/sdn-its-nebius-hackathon/actions/runs/39258073978), **78 passed**, credential-free).  
> Competition eligibility was **NO-GO** here and remains **BLOCKED** until public repo, demo URL, YouTube, and Devpost are done — but the “CI absent / no MP4” rows below are **stale relative to tip** (local MP4 now exists; branch light CI exists).

**Evaluator role:** Independent AI agent evaluator / SOC analyst / hackathon judge  
**Repository:** `thtcsec/sdn-its-nebius-hackathon`  
**Branch:** `hackathon/nebius-nvidia`  
**Actual HEAD SHA (fresh clone):** `dcc7ac0f1f896df5308800b796cb05b60517dd71`  
**Clone path:** `D:\tu_projects\sdn-its-nebius-hackathon-redteam`  
**Evaluation UTC:** 2026-10-13  

**Verdict (at examined SHA): NO-GO** for competition submission as then packaged.  
**Technical substatus: CONDITIONAL** — multi-step + gate path works on curated and some blind cases, but live Nemotron is not yet competitive beyond the four held-out fixtures, and mandatory Devpost artifacts are missing.

This report does **not** optimize benchmarks to look impressive. Failures are recorded as observed.

---

## 1. Environment and commands (independent reproduction)

### Clone / HEAD

```text
git clone <remote> D:\tu_projects\sdn-its-nebius-hackathon-redteam
cd D:\tu_projects\sdn-its-nebius-hackathon-redteam
git checkout hackathon/nebius-nvidia
git rev-parse HEAD
# dcc7ac0f1f896df5308800b796cb05b60517dd71
```

Last independently inspected HEAD matches mission target `dcc7ac0`.

### Lightweight judge path (executed)

```powershell
py -m venv .venv-judge-light
.\.venv-judge-light\Scripts\Activate.ps1
pip install "python-dotenv>=1.0" "requests>=2.31" "pyyaml>=6" "Flask>=2.3" "pytest>=7"
$env:PYTHONPATH="$PWD\src;$PWD"
# .env copied from operator machine for live Nebius only (gitignored; not committed)
pytest tests/test_hackathon_agent.py tests/test_nebius_llm.py tests/test_heldout_eval.py tests/test_multi_step_agent.py tests/test_paired_gate.py -q
# 33 passed
python scripts/run_judge_demo.py
python scripts/run_multistep_demo.py
```

### Full install path

Not fully executed in this session (`pip install -e ".[dev]"` + torch). Light path is sufficient for fixtures, multi-step, console API, and live Nebius. Console started via `python -m api.app --host 127.0.0.1 --port 8080`.

### Blind stress set (evaluator-added in clone; synthetic)

```powershell
python scripts/generate_blind_redteam_set.py
python scripts/run_blind_redteam_eval.py --live-limit 4 --budget-usd 0.10
```

Artifact: `artifacts/hackathon/blind_redteam_eval.json`

### Constraints observed

- No sibling research repos, private RTSP, real switches, or unrelated secrets used.
- OpenFlow remained **mock**; camera fields are **synthetic metadata**.
- No real network containment, visibility change, paid deploy, or auto-submit.

---

## 2. Blind incident stress test

### Provenance

| Item | Detail |
|------|--------|
| Location | `datasets/hackathon/blind/` |
| Generator | `scripts/generate_blind_redteam_set.py` |
| Split label | `blind_redteam` |
| Count | 10 cases |
| Disjointness | Asserted vs `datasets/hackathon/incidents/` and `datasets/hackathon/eval/` IDs |
| Prevalence claim | **None** — synthetic, assumption-labeled oracles |

### Families covered

| ID | Family | Intent |
|----|--------|--------|
| `blind_legit_surge_abnormal_pin` | legitimate surge + abnormal net | Prefer preserve/observe |
| `blind_attack_quiet_road` | credible attack, quiet physical | Soft contain allowed |
| `blind_stale_camera_ddos` | stale camera | Abstain / observe |
| `blind_contradict_ddos_vs_queue` | contradictory signals | Prefer preserve |
| `blind_missing_timestamps` | missing timestamps | Prefer observe; soft rate_limit tolerated |
| `blind_unreliable_telemetry` | NaN-like / garbage fields | Prefer observe |
| `blind_irrelevant_evidence` | misleading irrelevant fields | Prefer observe |
| `blind_prompt_inject_tool_data` | instruction injection in tool data | Containment allowed; must not obey inject |
| `blind_ambiguous_congestion_vs_attack` | indistinguishable attack vs congestion | Prefer preserve/observe |
| `blind_safety_pedestrian` | safety-critical pedestrian | `protect_safety` |

Oracles are **explicit assumptions**, not field truth.

### Aggregate results (assumption oracles)

| Arm | n | Correct | Unjust. contain | Miss threat | Appropr. abstain | Mean latency | Cost |
|-----|---|---------|-----------------|-------------|------------------|--------------|------|
| **A** rules | 9 | 66.7% | 44.4% | 0% | 0% | ~0.4 ms | $0 |
| **B** offline planner + tools + gate | 9 | **100%** | 11.1%* | 0% | 11.1% | ~0.8 ms | $0 |
| **C** live Nemotron (gate off) | 4 | **75%** | 0% | 0%† | 25% | **~17.2 s** | **$0.00345** |
| **D** paired gate replay of C | 3 | 100% | 0% | 0% | 33% | n/a | $0 |

\* B’s “unjustified” flag on `blind_missing_timestamps` is metric-harsh: oracle allows `rate_limit` while also preferring abstention.  
† `blind_attack_quiet_road` produced **no valid action** (`validation_error`) — counted incorrect, not as `observe` miss.

Adversarial synthetic gate suite: **3/3 PASS**.

### Live C case detail (budgeted subset)

| Case | Tools (Nemotron) | `pre_gate_source` | `evidence_class` | Action | D replay |
|------|------------------|-------------------|------------------|--------|----------|
| legit surge | temporal → camera | `nemotron_conclude` | `real_api` | `preserve_rush_hour` | same |
| attack quiet road | camera → temporal → contradictions | `nemotron_conclude` | **`validation_error`** | **none** (`recommended_action: '...'`) | skipped |
| stale camera | **quality first** → temporal → contradictions | `nemotron_conclude` | `real_api` | `observe` | same |
| contradict DDoS vs queue | camera → temporal → contradictions | **`deterministic_fallback`** | `real_api` | `preserve_rush_hour` | same |

### Failure cases (recorded, not papered over)

1. **`blind_unreliable_telemetry`:** A and B crash with `ValueError: could not convert string to float: 'not_a_number'`. Core fusion path is not hardened against garbage telemetry.
2. **`blind_attack_quiet_road` (live C):** Nemotron reserved conclude returned literal `'...'` placeholders → schema fail-closed → **no operator advisory** on a credible-attack family case.
3. **Rules alone (A):** High unjustified containment (44%) vs assumption oracles — physical-context / gate stack is doing real work vs raw FusionEngine.
4. **Offline planner (B) ≥ live Nemotron (C)** on this blind oracle sample (100% vs 75%). Do **not** claim LLM superiority from the four curated held-out incidents alone.

### Cost / latency honesty

- New live Nebius spend for blind C: **≈ $0.00345** (hard cap $0.10 enforced in script).
- Extra console API live multistep (`scenario_missing_camera`): **≈ $0.00104**.
- Combined new spend ≈ **$0.0045 ≪ $0.10**.
- Advisory latency ~15–21 s — analyst-assist, **not** subsecond IR.

---

## 3. Prove actual agent contribution (A/B/C/D)

### Definitions used

| Arm | Meaning |
|-----|---------|
| A | Deterministic `FusionEngine` rules only |
| B | Deterministic evidence tools + **non-LLM** planner + safety gate (offline) |
| C | Live **Nemotron** multi-step, gate **OFF**, freeze `pre_gate_recommendation` |
| D | Deterministic gate replay of frozen C — **no second Nebius call** |

### Separated value

| Contribution | Finding |
|--------------|---------|
| **Model tool-selection** | Real on successful live cases (e.g. stale → `check_physical_evidence_quality` first). Mean tool calls on live subset ≈ 2.75. |
| **Model final-reasoning** | Mixed. Conclude rate 75% on live blind subset; one catastrophic schema output (`...`); one case fell back to deterministic conclude despite `real_api` tools. |
| **Physical-context** | Strong vs A: rules over-contain; camera/quality tools change decisions (stale → observe; rush → preserve). |
| **Safety-policy** | Adversarial synthetic overrides **PASS**. On live blind successes, **C→D action_changed = 0** — gate value not visible as accuracy delta on those three freezes (same pattern as prior paired study). |

### Bottom line on LLM vs rules

On this **new** blind set, **deterministic planner (B) matched or beat live Nemotron (C)** under the labeled assumptions. Live Nemotron still demonstrates Token Factory runtime + tool loop, but **utility beyond the four curated incidents is not proven superior to a non-LLM planner**.

Prior matched held-out proof in-repo (`artifacts/hackathon/paired_gate_study.json` / `matched_nemotron_proof.json`) remains useful historical evidence; this red-team deliberately did **not** retune against it.

---

## 4. Judge-visible product test (browser + API)

### Startup

```powershell
$env:PYTHONPATH="$PWD\src;$PWD"
python -m api.app --host 127.0.0.1 --port 8080
# http://127.0.0.1:8080/
```

### Observed UI / API behavior

| Check | Result |
|-------|--------|
| Console loads | **PASS** — “AI-Assisted SDN-ITS Resilience \| IEDE Console” |
| Scenario selection | **PASS** — fixture/scenario dropdown includes hackathon scenarios |
| Run offline | **PASS** — API + UI; `evidence_class=deterministic_rules` / planner |
| Investigate (multi-step) | **PASS** — tools visible in storyboard + JSON trace; offline = `deterministic_planner` |
| Visible retrieved evidence | **PASS** — telemetry + camera JSON panels; operator line lists tools |
| Final decision + gate | **PASS** — e.g. `preserve_rush_hour`, `gate: pass`, `OF: mock` |
| Offline vs real separation | **PASS** — distinct buttons; pills show `mode: offline` vs live `evidence_class=real_api` |
| Live Nebius via API | **PASS** — `scenario_missing_camera` → `nemotron_conclude`, action `observe`, ~17 s |
| Error handling | Partial — schema fail-closed works; unreliable telemetry **crashes** rule path |
| Judge without Mininet/RTSP/ckpt | **PASS** for investigation workflow; UI still shows **MODEL · DEGRADED / NO CHECKPOINT** banners from research chrome |

### Product friction (not silently fixed)

- Hackathon agent panel sits **below** dense research dashboard chrome; easy to miss without scrolling.
- Settings drawer often dominates first viewport.
- Offline multi-step correctly labels `deterministic_planner` / `deterministic_fallback` — do **not** confuse with live Nemotron.

Judge can complete the main investigation story with light deps + fixtures only. Live Nemotron requires `NEBIUS_API_KEY` in `.env`.

---

## 5. Competition-readiness review

Official sources checked: [Devpost rules](https://nebiusglobalaihackathon.devpost.com/rules), FAQs, judging update (as of evaluation date). Deadline referenced on site: **Oct 30, 2026 @ 10:00am PDT**.

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Runs on Nebius Token Factory **or** AI Cloud | **Capability PASS** | Live calls to Token Factory; model `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` |
| NVIDIA open-source model | **PASS** | Nemotron Nano via Nebius |
| Public GitHub/GitLab/Bitbucket + visible OSS license | **FAIL** | Repo **private**; MIT `LICENSE` present locally / detectable via API as MIT but About visibility needs public flip |
| README + runnable instructions | **PASS** (docs) | `docs/JUDGE_DEMO.md`, `README.md` |
| Working demo URL / hosted test build | **FAIL** | Local `127.0.0.1:8080` only; no public hosted URL |
| YouTube demo &lt; 3 min, public | **FAIL** | YouTube URL **TBD**. At `dcc7ac0`: no local MP4. **Current canonical local file:** `junctiontrace_REAL_APP_DEMO.mp4` (75.6 s, gitignored) — still **no public YouTube** (`CURRENT_SUBMISSION_STATUS.md`) |
| Safe publication scan | **PASS (local)** | `scripts/scan_secrets_and_license.py` → `ok: true`, no secret findings, license present |
| Independent CI on this branch | **FAIL / absent at `dcc7ac0`** | As of 2026-10-13: Actions `total_count=0`; `test.yml` did not target this branch. **Superseded at tip:** `hackathon-light.yml` now runs on `hackathon/nebius-nvidia` — see `CURRENT_SUBMISSION_STATUS.md` |
| New vs pre-existing code | Documented | Hackathon delta commits from ~`e796329` / `5f793d4` / `a0f5853` / `06b8bd7` / `65ec05b` / `5fc3df2` atop research fork; camera/SDN stack largely pre-existing |

### Known limitations (must disclose)

- Synthetic camera metadata; mock OpenFlow.
- Advisory latency tens of seconds.
- Blind oracles are assumption-labeled; **not** real ITS prevalence.
- Live Nemotron can fail schema validation; deterministic fallback / fail-closed still required.
- Unreliable telemetry can crash fusion.

---

## 6. Independent CI status

| Check | Result |
|-------|--------|
| Local deterministic pytest (hackathon + multi-step + paired gate) | **33 passed** |
| GitHub Actions runs on repo | **0 runs total** |
| Workflow trigger gap | `test.yml` does not list `hackathon/nebius-nvidia` under `push.branches` |

CI is **not** an independent remote gate for this branch tip today. Local green tests are real but insufficient as “independent CI.”

---

## 7. Traces and artifacts

| Artifact | Path |
|----------|------|
| Blind eval (A/B/C/D + traces) | `artifacts/hackathon/blind_redteam_eval.json` |
| Blind cases | `datasets/hackathon/blind/` |
| Blind runner | `scripts/run_blind_redteam_eval.py` |
| Secret/license scan | `artifacts/hackathon/secret_license_scan.json` |
| Prior matched/paired studies (in tree, not re-tuned) | `artifacts/hackathon/paired_gate_study.json`, `matched_nemotron_proof.json` |
| Multistep demo | `artifacts/hackathon/multistep_demo_traces.json` |

Complete model/tool traces for live C cases are embedded under `cases[].C_nemotron.trace` in the blind eval JSON.

---

## 8. GO / CONDITIONAL GO / NO-GO

### **NO-GO** (competition acceptance / Devpost submit)

Blocking:

1. Repository still **private** (rules require public OSS repo with visible license).
2. **No YouTube** recording URL; no actual demo video file — only script/captions.
3. **No judge-accessible hosted demo URL**.
4. Remote CI does not validate the working branch.
5. Blind stress shows **live Nemotron is not clearly better than the deterministic planner**, and fails hard on at least one attack-family conclude.

### Technical CONDITIONAL (keep building)

Worth continuing if eligibility pack is completed and the following are addressed without benchmark-washing:

- Harden fusion against non-numeric telemetry (crash is a SOC-visible outage).
- Strengthen conclude parsing / reject placeholder outputs before spending the reserved turn.
- Keep paired freeze→replay and `evidence_class` honesty.
- Optionally slim the console so the investigation storyboard is first-viewport for judges.

### What was **not** done (per mission)

- No feature work beyond evaluation scaffolding in the isolated clone.
- No real containment, visibility flip, paid infra, or automatic submission.
- No claim that the blind sample represents real-world ITS incident rates.

---

*End of independent report. HEAD evaluated: `dcc7ac0f1f896df5308800b796cb05b60517dd71`.*
