# WINNING_EVIDENCE — Prove the value of Nemotron

**Narrative:** A traffic surge is not always an attack. Before disrupting a cyber-physical system, investigate the evidence.  
**Intended user:** ITS network operator / SOC analyst who must decide whether PacketIn/RSU-edge surges justify containment without breaking legitimate mobility traffic.  
**Track:** Best Apps and Agents (overall-prize ambitions; not claimed as winner).

---

## 1. Remote commit SHA

| Item | Value |
|------|-------|
| Local + remote HEAD | **`a0f58532c9ff6a7ca647c817e2ffd8c92c1b1316`** (multi-step landing) |
| Follow-up proof commit | *(this sprint — see `git log -1` after push)* |
| Branch | `hackathon/nebius-nvidia` |
| Remote | `https://github.com/thtcsec/sdn-its-nebius-hackathon` |
| Visibility | **PRIVATE** (unchanged; no flip without owner approval) |
| Verify on GitHub | `gh api repos/thtcsec/sdn-its-nebius-hackathon/commits/a0f58532c9ff6a7ca647c817e2ffd8c92c1b1316` |

**Blocker cleared:** Independent reviewers previously saw `fedf93b` because `a0f5853` was local-only (`ahead 1`). Push completed: `fedf93b..a0f5853` → `origin/hackathon/nebius-nvidia`.

---

## 2. Actual tool traces (live Nemotron)

Source: `artifacts/hackathon/matched_nemotron_proof.json`  
Model: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` · `evidence_class: real_api` · OF: **mock** · Camera: **synthetic metadata**

Nemotron **chose tools on 100%** of B/C/D runs (`nemotron_chose_tools_rate: 1.0`). Premature conclude-without-tools is rejected; the model must emit `action=tool_call`.

### Matched case tool sequences (C = net+cam, live)

| Case | Family | Tools Nemotron selected (order) | Final action |
|------|--------|----------------------------------|--------------|
| `eval_legit_cong_01` | legitimate surge | retrieve_network → inspect_camera → compare_temporal → check_physical_quality | `preserve_rush_hour` |
| `eval_suspicious_01` | plausible attack | retrieve_network → inspect_camera → compare_temporal → identify_contradictions | `rate_limit` |
| `eval_missing_01` | stale/missing camera | **check_physical_evidence_quality** → compare_temporal → inspect_camera → identify_contradictions | `observe` |
| `eval_conflict_01` | contradictory | inspect_camera → retrieve_network → compare_temporal → identify_contradictions | `preserve_rush_hour` |

**Contribution signal:** On missing evidence, Nemotron’s *first* tool was `check_physical_evidence_quality` — not a static context dump. On conflict/legit surge, camera inspection + contradictions precede preserve. Without camera (arm B), the same suspicious case **only observes** (missed soft containment) while C/D correctly `rate_limit`.

Full per-arm traces (detect → uncertainty → select_evidence_tool → retrieve_validate → reason → policy_gate → audit) are embedded under each case in the JSON artifact.

---

## 3. Matched A/B/C/D table (live Nemotron for B/C/D)

Exact same preselected IDs for all arms:  
`eval_legit_cong_01`, `eval_suspicious_01`, `eval_missing_01`, `eval_conflict_01`

| Arm | Definition | Correct | Unjustified containment | Miss threat | Useful evidence req. | Mean tools | Mean latency | Est. cost |
|-----|------------|---------|-------------------------|-------------|----------------------|------------|--------------|-----------|
| **A** | Rules only | 75% (3/4) | **25%** (1/4) | 0% | 0% | 0 | ~0.6 ms | $0 |
| **B** | Live Nemotron, network only | 75% (3/4) | 0% | **25%** (1/4) | 100% | 3.75 | ~13.5 s | ~$0.0021 |
| **C** | Live Nemotron, net + camera | **100%** (4/4) | 0% | 0% | 50% | 4.0 | ~12.9 s | ~$0.0021 |
| **D** | Live Nemotron, net + camera + gate | **100%** (4/4) | 0% | 0% | 50% | 4.0 | ~13.x s | ~$0.0021 |

**Total live spend:** ≈ **$0.00631** (hard budget $0.10; not exhausted).

### Action matrix

| Case | A rules | B net-only | C net+cam | D +gate |
|------|---------|------------|-----------|---------|
| legit surge | preserve | observe | preserve | preserve |
| suspicious | rate_limit | observe | rate_limit | rate_limit |
| missing cam | **rate_limit** (unjustified) | observe | observe | observe |
| conflict | preserve | observe | preserve | preserve |

**Operator value:** Rules alone falsely contain when the camera is missing (`eval_missing_01`). Nemotron+camera abstains. Network-only Nemotron under-responds to a credible LOFT-like case; adding camera restores soft containment. Investigation reduces unsupported operational decisions.

---

## 4. Real API evidence

| Artifact | Role |
|----------|------|
| `artifacts/hackathon/matched_nemotron_proof.json` | Matched live A/B/C/D + full traces |
| `artifacts/hackathon/ablation_real_summary.json` | Prior budgeted real subset (redacted) |
| `artifacts/hackathon/real_api_evidence_redacted.json` | Verify / vertical-slice redacted bundle |
| Token Factory | `https://api.tokenfactory.nebius.com/v1` |
| Model | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` |

No fabricated completions. Fail-closed without credentials.

---

## 5. Model contribution analysis

| Question | Evidence |
|----------|----------|
| Does Nemotron only consume a fixed bundle? | **No** — emits sequential `tool_call` JSON; tools execute app logic; results return in-loop |
| Does camera context help? | **Yes on this matched set** — C/D 100% vs B 75%; B misses threat on suspicious; C/D rate_limit after camera tools |
| Does the gate still matter? | On this n=4, C and D agreed; gate remains authoritative for unsafe escalation / insufficient evidence (see scenarios + `safety.py`) |
| Offline planner 92%? | **Separate** — `ablation_offline.json` `deterministic_planner`. **Never advertise as Nemotron accuracy.** |

---

## 6. Latency / cost

| Metric | Value |
|--------|-------|
| Matched live total cost | ~$0.00631 |
| Budget cap | $0.10 |
| B/C/D mean latency | ~13 s / case (multi model rounds) |
| Tokens (B+C+D approx) | ~22k + ~24k + ~similar (see JSON) |
| Rules latency | &lt;1 ms |

---

## 7. Judge reproduction (no private cameras / Mininet / checkpoint)

```powershell
git clone https://github.com/thtcsec/sdn-its-nebius-hackathon.git
cd sdn-its-nebius-hackathon
git checkout hackathon/nebius-nvidia
git rev-parse HEAD   # expect a0f5853 or newer proof commit
py -m venv .venv-judge-light
.\.venv-judge-light\Scripts\activate
pip install "python-dotenv>=1.0" "requests>=2.31" "pyyaml>=6" "Flask>=2.3" "pytest>=7"
$env:PYTHONPATH="$PWD\src;$PWD"

# Offline (no key): multi-step traces + planner ablation (NOT Nemotron accuracy)
python scripts/run_multistep_demo.py
python scripts/run_ablation_study.py --skip-real --allow-containment-in-demo

# Console (mock OF)
.\scripts\dev.ps1
# → http://127.0.0.1:8080/  → Hackathon board → multi-step scenarios

# Live matched proof (needs NEBIUS_API_KEY in repo-root .env; ≤ $0.10)
python scripts/run_matched_nemotron_proof.py --budget-usd 0.10 --allow-containment-in-demo
pytest tests/test_multi_step_agent.py tests/test_hackathon_agent.py tests/test_nebius_llm.py tests/test_heldout_eval.py -q
```

Docs: `docs/JUDGE_DEMO.md`, `COMPETITION_DELTA_REPORT.md`, `docs/NEBIUS_NVIDIA_FEEDBACK.md`.

---

## 8. Video and release checklist

| Submission item | Status | Notes |
|-----------------|--------|-------|
| Public GitHub + MIT | **BLOCKED** | MIT present; visibility private until owner approval (`docs/PUBLIC_RELEASE_CHECKLIST.md`) |
| Working demo / test-build URL | **LOCAL READY** | `http://127.0.0.1:8080/` via `.\scripts\dev.ps1`. Hosted URL not deployed (no paid deploy without approval) |
| YouTube &lt;3 min | **SCRIPT READY / URL TBD** | `docs/DEMO_VIDEO.md` |
| Token Factory + Nemotron disclosure | **READY** | README + this file + feedback draft |
| Pre-existing project explanation | **READY** | `docs/HACKATHON_CONTRIBUTIONS.md` |
| Nebius/NVIDIA feedback text | **DRAFT** | `docs/NEBIUS_NVIDIA_FEEDBACK.md` — do not submit without approval |
| English materials | **PASS** | |

### Demo video shot list (product story)

1. Title: surge ≠ attack — investigate before disrupt  
2. Console: `scenario_rush_vs_attack` multi-step tools → preserve  
3. `scenario_missing_camera`: quality tool → observe (vs rules that would contain)  
4. Terminal: matched table C/D 4/4 vs A unjustified containment  
5. Honesty: synthetic camera metadata, mock OF, offline 92% ≠ Nemotron  
6. End: judge commands + repo (after public)

---

## 9. Unresolved failures / risks

1. **Public repo / YouTube / hosted demo URL** still required for Devpost eligibility — need owner approval.  
2. Matched live n=4 is **meaningful but small**; do not overclaim statistical superiority for overall prize.  
3. Arm B (net-only) over-abstains on suspicious traffic (miss_threat 25%) — shows camera value, but also that Nemotron without physical context is conservative.  
4. Full pytest suite needs torch in some environments; judge light path does not.  
5. Hosted demo not provisioned (Nebius Serverless / tunnel) without approval.  
6. Independent review of older HEAD is obsolete after push; request re-review at `a0f5853`+.

---

## Separation banner (mandatory)

```
OFFLINE deterministic planner (ablation_offline.json): D≈92% on N=25
  → NOT Nemotron accuracy. Do not put this number in the pitch as model performance.

LIVE matched Nemotron proof (matched_nemotron_proof.json): C/D = 4/4 on 4 cases
  → This is the Nemotron value evidence. Still small-n.
```
