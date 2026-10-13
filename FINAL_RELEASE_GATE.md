# FINAL_RELEASE_GATE — Nebius × NVIDIA Hackathon

**Branch:** `hackathon/nebius-nvidia`  
**Base verified:** `65ec05b`  
**This freeze tip:** 5fc3df247ecd6f2fd5ec47d8551b4d7b90e37ac3  
**Visibility:** PRIVATE — do not flip or submit without owner approval.

**Narrative:** A traffic surge is not always an attack. Before disrupting a cyber-physical system, investigate the evidence.  
**User:** ITS network operator / SOC analyst who must avoid unsupported containment and missed threats.

---

## Acceptance checklist

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Paired policy-gate comparison causally valid | **PASS** — D = freeze C pre-gate rec → replay gate; no second Nemotron call |
| 2 | Live Nemotron tool calls + final decisions | **PASS** — `C_pre_gate_nemotron_rate=1.0` on matched 4 |
| 3 | No mislabeled deterministic accuracy | **PASS** — offline planner scores excluded from this study |
| 4 | Meaningful operator pain demonstrated | **PASS** — storyboard + four situations + unjustified-contain / miss-threat metrics |
| 5 | No unsafe real containment | **PASS** — mock OpenFlow; demo blocks destructive intent |
| 6 | Independently reproducible demo | **PASS** — light venv + fixtures/scenarios; no RTSP/Mininet/ckpt |

---

## Mission A — Paired policy-gate replay

**Artifact:** `artifacts/hackathon/paired_gate_study.json`  
**Script:** `python scripts/run_paired_gate_study.py --budget-usd 0.10 --allow-containment-in-demo`  
**Spend:** ≈ **$0.00735** / $0.10 cap  

### Method (causal)

1. **B:** live Nemotron, network-only (+gate) — separate inference for camera ablation.  
2. **C:** live Nemotron, network+camera, **gate OFF** — freezes `pre_gate_recommendation` + evidence bundle + trace.  
3. **D:** deterministic `replay_recommendation_pair` of that frozen advisory through the safety gate — **no Nebius recall**.  
4. **Adversarial (synthetic):** forced DROP / rush de-escalate / safety force — prove enforcement; **not** live accuracy.

### Matched live summary (n=4)

| Path | Correct | Unjustified contain | Miss threat | Appropr. abstain | Notes |
|------|---------|---------------------|-------------|------------------|-------|
| B net-only | 75% | 0% | 25% | 25% | Live Nemotron |
| C ungated (frozen) | 75% | 0% | 25% | 25% | Live Nemotron conclude **100%** |
| D gated replay | 75% | 0% | 25% | 25% | Same advisory as C |

| Gate causality metric | Value |
|----------------------|-------|
| Paired override frequency | **0%** (0/4) |
| Override justified rate | n/a (no overrides on this live sample) |
| Model-generated conclude (C) | **100%** |
| Deterministic fallback (C) | **0%** |
| Adversarial enforcement | **3/3 PASS** |

**Honest read:** On this live matched set, Nemotron’s pre-gate actions already matched the gated outcome — so **C→D accuracy cannot be attributed to the gate**. Gate value is proven by **adversarial synthetic overrides** (insufficient evidence → observe; rush DROP → de-escalate; safety_critical → protect_safety), not by this n=4 accuracy delta.

### Latency / cost (advisory workflow)

| Metric | Value |
|--------|-------|
| B mean latency | ~16.5 s |
| C mean latency | ~20.6 s |
| Total est. cost | ~$0.00735 |
| Claim | **Analyst advisory** (seconds), **not** subsecond IR |

Camera metadata: **synthetic**. OpenFlow: **mock**.

---

## Mission B — Autonomous investigation loop

Four held-out situations (same IDs):

| ID | Situation | Typical tools (live C) |
|----|-----------|-------------------------|
| `eval_legit_cong_01` | Legitimate congestion | network → camera → quality / temporal |
| `eval_suspicious_01` | Plausible attack | network → camera → contradictions |
| `eval_missing_01` | Stale/missing camera | **quality first** → observe |
| `eval_conflict_01` | Contradictory evidence | camera ↔ network contradictions |

Loop shown in traces:  
`detect → identify_uncertainty → select_evidence_tool → retrieve_validate → (final_reason) → nemotron_conclude → policy_gate → audit`

Demo scenarios (offline story): `datasets/hackathon/scenarios/` + `scripts/run_multistep_demo.py`.

---

## Mission C — Judge console

UI storyboard (7 steps) on the Hackathon board:

1. Alarm · 2. Missing · 3. Tool · 4. Retrieved · 5. Model · 6. Policy · 7. Why it matters  

```powershell
.\scripts\dev.ps1
# http://127.0.0.1:8080/ → Hackathon · Incident agent → Investigate (multi-step)
```

No private RTSP, Mininet, or classifier checkpoint required for this path.

---

## Mission D — Submission package

| Item | Location / status |
|------|-------------------|
| MIT license | `LICENSE` — present |
| Public-release checklist | `docs/PUBLIC_RELEASE_CHECKLIST.md` |
| Secrets scan | `python scripts/scan_secrets_and_license.py` |
| Working demo URL | **Local:** `http://127.0.0.1:8080/` — **hosted URL not deployed** (no paid deploy without approval) |
| Pitch / video script | `docs/DEMO_VIDEO.md` (&lt;3 min) |
| Nebius/NVIDIA feedback | `docs/NEBIUS_NVIDIA_FEEDBACK.md` |
| Offline vs live separation | Offline planner ≠ Nemotron; this gate study is live + synthetic adversarial |
| Contributions vs research | `docs/HACKATHON_CONTRIBUTIONS.md` |
| Prior evidence | `WINNING_EVIDENCE.md`, `COMPETITION_DELTA_REPORT.md` |

### English pitch (30s)

> When an RSU-edge PacketIn surge hits, dropping traffic can strand vehicles — but ignoring a real attack is worse. Our agent uses NVIDIA Nemotron on Nebius Token Factory to **investigate**: it picks evidence tools, reads synthetic same-zone camera metadata, concludes, then a deterministic safety gate remains authoritative. Mock OpenFlow. Built for ITS operators who need supported decisions, not a chatbot.

### YouTube script pointer

Follow `docs/DEMO_VIDEO.md`: rush vs attack → missing camera → storyboard → paired-gate honesty (adversarial override demo) → limitations.

---

## Judge reproduction

```powershell
git clone https://github.com/thtcsec/sdn-its-nebius-hackathon.git
cd sdn-its-nebius-hackathon
git checkout hackathon/nebius-nvidia
git rev-parse HEAD
py -m venv .venv-judge-light
.\.venv-judge-light\Scripts\activate
pip install "python-dotenv>=1.0" "requests>=2.31" "pyyaml>=6" "Flask>=2.3" "pytest>=7"
$env:PYTHONPATH="$PWD\src;$PWD"
python scripts/run_multistep_demo.py
pytest tests/test_paired_gate.py tests/test_multi_step_agent.py tests/test_hackathon_agent.py -q
.\scripts\dev.ps1
# Optional live (≤ $0.10):
python scripts/run_paired_gate_study.py --budget-usd 0.10 --allow-containment-in-demo
```

---

## Remaining blockers (owner approval required)

1. Make repository **public** (MIT visible on GitHub About).  
2. Upload YouTube demo (&lt;3 min); paste URL in `docs/DEMO_VIDEO.md`.  
3. Provide **hosted** working demo URL (or judge credentials) — not deployed here.  
4. Submit Devpost + paste `docs/NEBIUS_NVIDIA_FEEDBACK.md`.  
5. Do **not** advertise offline planner ~92% as Nemotron accuracy.  
6. Do **not** claim gate improves live n=4 accuracy when override frequency is 0 — cite adversarial enforcement instead.

---

## Feature freeze

After this commit lands on `origin/hackathon/nebius-nvidia`, treat product features as **frozen** pending owner decisions on visibility, video, hosting, and submission.
