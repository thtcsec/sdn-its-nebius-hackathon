# Independent adversarial hackathon review

**Role:** Independent judge-style reviewer (not the implementing agent)  
**Scope:** `D:\tu_projects\sdn-its-nebius-hackathon` only  
**Reviewed HEAD:** `fedf93b84eea25903a337c70ddfba19c21c07af9` (`hackathon/nebius-nvidia`)  
**Baseline for hackathon delta:** `main...HEAD` (~81 files, +9431 / −156)  
**Remote visibility (verified):** **PRIVATE** — `https://github.com/thtcsec/sdn-its-nebius-hackathon`  
**Review date:** 2026-10-12  
**Rules source:** Nebius x NVIDIA Global AI Hackathon Official Rules (Devpost; Submission Period ends 2026-10-30 PT)

**Verdict (survival under independent judging):** **Would not currently clear mandatory submission gates.** Technical vertical slice and honesty hygiene are real and above many PoCs, but public repo, YouTube demo, and hosted working-demo URL are missing. Even if those gates pass later, measurable Nemotron *value over rules* is not yet demonstrated at a prize-competitive confidence level.

This document does **not** declare the project award-winning. No secrets were read from sibling repositories. No code, tests, config, git history, or evidence artifacts were modified for this review (except creation of this review file).

---

## Commands used (exact)

```powershell
cd D:\tu_projects\sdn-its-nebius-hackathon
git rev-parse HEAD
git status -sb
git log --oneline main..HEAD
git diff --stat main...HEAD
gh repo view --json visibility,url,isPrivate
```

Reproduce (not re-run for this review; evidence already on disk):

```powershell
# Offline / fail-closed path
python scripts/run_judge_demo.py
python scripts/run_heldout_eval.py --skip-real
python scripts/run_hackathon_benchmark.py --mode offline --allow-containment-in-demo
pytest tests/test_hackathon_agent.py tests/test_nebius_llm.py tests/test_heldout_eval.py -q

# Real Token Factory (requires local .env; costs money)
python scripts/verify_nebius_nemotron.py
python scripts/run_heldout_eval.py --real-limit 5 --budget-usd 0.05 --allow-containment-in-demo
```

**Working tree note:** `artifacts/hackathon/benchmark_offline.json` shows as modified vs HEAD at review time (`git status -sb`). Treat committed artifacts as authoritative unless regenerated deliberately.

---

## 1. User and painful real-world problem

| Item | Assessment | Confidence |
|------|------------|------------|
| **Intended user** | Edge / RSU / SDN-ITS operators and researchers who must mitigate control-plane or edge DDoS-like surges without blackholing legitimate rush-hour mobility traffic | **Medium–High** (stated in research packaging + `docs/IEDE_Report_Summary.md`, `docs/JUDGE_DEMO.md`) |
| **Pain** | Coarse telemetry (PacketIn surge, dominance) looks similar for attacks and legitimate congestion; permanent DROP harms V2X/ITS service; camera/physical context can reduce false containment | **Medium** (credible CPS/ITS problem; not validated with operator interviews or field deployment in this repo) |
| **Hackathon product surface** | Cyber–physical *investigation agent*: rule fusion + Nemotron advisory JSON + schema/safety gate + mock OpenFlow PolicyEngine + console board | **High** (code + docs) |

**What is *not* the demonstrated product:** live switch PacketIn reduction, real RTSP/YOLO camera loop for the judge path, or production SOAR replacement.

---

## 2. Comparison to existing solutions / baselines

| Baseline | What it is | Overlap with this project | Differentiator claimed here | Verifiable refs |
|----------|------------|---------------------------|-----------------------------|-----------------|
| **A. Classic SDN IDS → OpenFlow mitigation** | Suricata/Ryu (or similar) detect floods/scans and install drop/rate-limit FlowMods | Detect → contain via SDN | Same-zone **camera/physical** fusion + **rollback** narrative; LLM advisory layer | [ozan2003/sdn_intrusion_mitigation](https://github.com/ozan2003/sdn_intrusion_mitigation); SDN+Suricata IDS demos (e.g. IDSforSDN-style stacks) |
| **B. NVIDIA Morpheus** | GPU cybersecurity AI pipelines on network telemetry; real-time inspection / anomaly pipelines; optional DPU telemetry | Network AI for security | This entry is **LLM investigation + ITS camera fusion + reversible policy**, not Morpheus-scale telemetry AI | [Morpheus docs](https://docs.nvidia.com/morpheus/); [NVIDIA Tech Blog intro](https://developer.nvidia.com/blog/cybersecurity-framework-an-introduction-to-nvidia-morpheus/) |
| **C. LLM-assisted SOC / SOAR copilots** | Sentinel / SecOps Gemini / Security Copilot draft playbooks; human approval gates; policy verification research (SOCpilot) | LLM proposes actions; deterministic policy should remain authoritative | Domain is **SDN-ITS cyber–physical**, not enterprise SIEM tickets; Nebius Token Factory + Nemotron Nano | [Microsoft Sentinel AI playbooks](https://learn.microsoft.com/en-us/azure/sentinel/automation/generate-playbook); [Google SecOps Gemini playbooks](https://cloud.google.com/chronicle/docs/soar/respond/working-with-playbooks/create-edit-playbook-with-gemini); [SOCpilot arXiv](https://ar5iv.labs.arxiv.org/html/2605.05501) |

**Fair takeaway:** The *problem framing* (false-positive SDN mitigation in transport/edge networks) is more distinctive than the *LLM pattern* (structured advisory + gates), which is now common in SOC tooling and research.

---

## 3. Claimed innovations that already exist elsewhere

| Claim / motif (as marketed in hackathon docs) | Exists elsewhere? | Notes |
|-----------------------------------------------|-------------------|-------|
| LLM drafts mitigation / IR actions | **Yes** | SOAR copilots, Security Copilot, Gemini playbooks |
| Schema validation + fail-closed on bad model JSON | **Yes** (pattern) | Standard for tool-calling agents; SOCpilot-style policy verification is a stronger research cousin |
| Deterministic gate that blocks unsafe escalation | **Yes** | Approval gates / policy clamps in SOAR; this repo’s clamp is explicit in `safety.py` |
| SDN OpenFlow temporary contain + rollback | **Yes** (research + OSS SDN demos) | Inherited baseline more than hackathon invention |
| Camera as physical-context sensor for cyber decisions | **Partially** | Cyber-physical / IT-OT SDN literature exists; *same-zone RSU camera × PacketIn fusion* is a narrower niche (stronger originality than “LLM + gate”) |
| Nebius Token Factory + NVIDIA Nemotron in the loop | **Required track tech**, not unique IP | Differentiation must come from *use*, not mere presence |

**Honest originality residual:** packaging a **judge-reproducible**, honesty-labeled cyber–physical investigation path (fixtures + held-out oracle + mock OF + real Nano evidence) on top of a prior SDN-ITS research stack — not a novel mitigation algorithm, and not a proven accuracy win for Nemotron.

---

## 4. Key technical claims vs code and runtime evidence

Legend: **PASS** / **FAIL** / **UNKNOWN** / **PARTIAL**

| Claim | Status | Evidence |
|-------|--------|----------|
| Real Nebius Token Factory runtime call | **PASS** | `artifacts/hackathon/real_api_evidence_redacted.json`: `evidence_class: real_api`, model `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, HTTP 200, `chatcmpl-eb2610a1-…`, list_models includes Nemotron IDs |
| Uses NVIDIA open-source model family (Nemotron) | **PASS** | Same artifact + client default path; OpenAI-compatible `https://api.tokenfactory.nebius.com/v1` |
| Structured validated recommendations | **PASS** | `src/sdn_its/llm/schema.py` + tests in `tests/test_nebius_llm.py` |
| Safety gates / demo blocks containment | **PASS** | `src/sdn_its/llm/safety.py` (`gate:deescalated_to_rule`, `gate:demo_block_containment`, `gate:forced_protect_safety`); fixture `07_unsafe_escalation_blocked` |
| Fail-closed without credentials / malformed | **PASS** | Fixtures `05_*`, `06_*`; offline evidence classes `validation_error`, `blocked_no_credentials` |
| OpenFlow remains non-destructive in demo | **PASS** (by design) | Mock OF default; demo_mode downgrades containment intentions |
| Nemotron improves decision accuracy vs rules | **FAIL / not supported** | Held-out: rules **84%** (21/25) vs Nemotron real_api **80%** (4/5). Docs correctly refuse this claim; README/status table is stale (see §7) |
| Offline benchmark proves accuracy | **FAIL if claimed; PASS if honesty-read** | `benchmark_offline.json` honesty_note: agreement ≠ accuracy; uses `synthetic_offline` |
| Held-out eval is disjoint from regression fixtures | **PASS** | `tests/test_heldout_eval.py` + `assert_disjoint_from_dev`; MANIFEST 25 IDs under `eval_*` |
| Judge path needs no RTSP / checkpoint | **PASS** (artifact) | `fresh_venv_judge_verify.json` / audit: checkpoint and camera inventory absent |
| Public demo / video for judges | **FAIL** | `docs/DEMO_VIDEO.md` YouTube URL **TBD**; repo **PRIVATE** |
| README status matches reality | **FAIL** | README still says Nebius key “Blocked”, vertical slice “Not started”, target Lightning — contradicted by Nano `real_api` evidence and commits through `fedf93b` |

### Evidence class map (do not conflate)

| Class | Meaning in this repo | Treat as accuracy? |
|-------|----------------------|--------------------|
| `real_api` | Live Token Factory completion | Yes (small N) |
| `synthetic_offline` | Fixture-embedded model JSON | **No** |
| `skipped_no_fake_offline` | Intentionally not faked | **No** |
| `mocked_transport` | Unit tests | **No** |
| `deterministic_rules` | FusionEngine path | Baseline only |
| `blocked_no_credentials` / `validation_error` | Fail-closed protocol | Reliability, not model accuracy |

### Structural limit on “AI decision power” (code)

From `gate_recommendation` in `safety.py`:

- LLM **may not escalate beyond** rule-fusion action when fusion is present.
- `demo_mode` (default) converts containment → `observe`.

So live Nemotron mostly contributes **rationale / bounded advice** inside a rule envelope, not independent stronger containment. That is safety-honest and simultaneously **caps Impact / Idea upside** unless storytelling focuses on *safer abstention / explanation under uncertainty*.

---

## 5. Tests, leakage, fairness of benchmarks

### Tests are meaningful? **PARTIAL → mostly yes for gates; weak for model quality**

| Suite | What it actually proves |
|-------|-------------------------|
| `tests/test_nebius_llm.py` | Schema extract/validate; gate de-escalate/protect; investigation wiring; **mocked** Nebius — labeled as non-real |
| `tests/test_hackathon_agent.py` | Offline fixtures: unsafe escalation blocked, malformed/API fail-closed, rush-hour no inappropriate containment, API routes, offline benchmark script exit 0 |
| `tests/test_heldout_eval.py` | ≥20 held-out cases, ID disjointness, oracle scorer unit logic, incidents README mentions regression |

**Missing as automated tests:** end-to-end `real_api` (correctly left to scripts — cost/flaky); statistical superiority of Nemotron; live OF; real camera.

### Evaluation leakage?

| Risk | Finding |
|------|---------|
| Dev fixture IDs in eval | **Mitigated** — disjoint IDs enforced |
| Embedded Nebius gold answers in eval | **Mitigated** — generator states no embedded completions except declared `force_mode` protocol probes |
| Oracle encodes same heuristics as FusionEngine | **Residual concern (MEDIUM)** — same authoring pipeline (`generate_heldout_eval.py`) labels oracles that largely agree with rule philosophy; rules scoring 84% may partly reflect **oracle–rule co-design**, not independent field labels |
| Offline synthetic JSON matching expected actions | **Regression only** — honest if not sold as accuracy (tests lean on `expected` flags in agent metrics) |
| Real_api subset selection | **N=5 budgeted** — underpowered; one miss (`eval_missing_01` rate_limit vs observe) flips narrative |

### Benchmark fairness

| Comparison | Fair? | Why |
|------------|-------|-----|
| Offline rule ↔ synthetic Nemotron agreement | **Fair as agreement only** | Not an accuracy bake-off |
| Held-out rules vs oracle (N=25) | **Reasonably fair for rules** | Synthetic inputs; oracle human-authored |
| Held-out Nemotron vs oracle (N=5 real) | **Underpowered / not fair for superiority claims** | Latency ~4.8s vs rules ~0.25ms; demo gates may still reshape actions depending on flags |
| Cost reported (~$0.0013 / 5 calls) | **Credible order-of-magnitude** | From usage × estimator in artifacts — not independently re-billed here |

---

## 6. Five new adversarial test cases (not in repo fixtures)

Do **not** add these to the repo to “make them pass.” Design-only for independent judging / future hardening.

1. **Stale-but-confident camera during LOFT**  
   Network: LOFT-like low-rate anomaly; camera: `analytics_valid=true`, high vehicle count, but `stale=true` and stream flapping.  
   Oracle: forbid hard DROP; prefer observe or soft rate_limit with explicit uncertainty.  
   Attacks: over-trust of stale physical “rush” narrative.

2. **Safety-critical physical + benign-looking network**  
   Network: `Benign` / quiet PacketIn; camera: `incident=true` / pedestrian in roadway zone.  
   Oracle: `protect_safety` (or observe + escalate human), never ignore physical incident because cyber is quiet.  
   Attacks: cyber-only decision bias.

3. **Model returns valid JSON with `temporary_drop` while rules say `preserve_rush_hour`**  
   Force real or injected completion.  
   Oracle: final action must not exceed rule rank; gated notes must include de-escalation.  
   Already partially covered by fixture 07 offline; **adversarial real_api** variant with rush-hour telemetry.

4. **Conflicting dominance: distributed sources + high camera queue + classifier “DDoS”**  
   Classic false-positive trap.  
   Oracle: preserve/observe unless second signal confirms.  
   Attacks: prompt/heuristic that “DDoS label ⇒ drop.”

5. **Token Factory partial failure: HTTP 200 with empty content / truncated JSON mid-object**  
   Distinct from fixture malformed string.  
   Oracle: fail-closed to rules; `ok=false`; no fabricated recommendation.  
   Attacks: treating empty success as observe with high confidence.

---

## 7. Mandatory competition submission requirements

Source: Official Rules — Project Requirements + Submission Requirements (Devpost).

| Requirement | Status | Notes |
|-------------|--------|-------|
| Working software using Nebius Token Factory **or** AI Cloud | **PASS** (capability) | Runtime path exists; judges need credentials or public demo |
| ≥1 NVIDIA OSS model (Nemotron etc.) | **PASS** | Nano 30B via Token Factory |
| Fits a track | **PASS / Best Apps and Agents** (best fit) | Physical AI would need ≥1 min hardware clip — **not** met; Coding track misfit |
| Significant update if pre-existing | **PARTIAL → PASS if submitted with `HACKATHON_CONTRIBUTIONS.md`** | Pre-existing SDN-ITS research; hackathon LLM/agent/eval clearly documented |
| **Public** GitHub/GitLab/Bitbucket + OSS license detectable | **FAIL** | Repo **PRIVATE**; MIT `LICENSE` present locally |
| README with setup + Nemotron/Token Factory highlight | **PARTIAL** | Setup exists; **status table stale/wrong**; model default text still Lightning |
| Working demo URL / hosted app / test build | **FAIL / UNKNOWN** | Local `127.0.0.1:8080` documented; no public hosted URL found |
| YouTube demo &lt;3 min, public | **FAIL** | `docs/DEMO_VIDEO.md` URL **TBD** |
| English materials | **PASS** | |
| Feedback on Nebius/NVIDIA tools (Devpost form) | **UNKNOWN** | Not verifiable from repo |
| Stage One viability (theme + required APIs) | **UNKNOWN → at risk** | Theme fit OK; **missing public artifacts** may fail administrative screening before rubric |

**Bottom line on gates:** As of HEAD + current visibility, submission is **not judge-ready** for Devpost eligibility even though the technical Token Factory call is real.

---

## 8. Rubric assessment (Stage Two criteria)

Assume Stage One somehow passed. Scores are **independent reviewer estimates** (1–5), equally weighted per rules. Not official scores.

| Criterion | Score | Confidence | Evidence-based rationale |
|-----------|-------|------------|--------------------------|
| **Technological Implementation** | **3.5 / 5** | Medium | Real Nano via Token Factory; clean client/schema/gate/agent; mock OF honesty; small live sample; README drift undermines perceived polish |
| **Design** | **2.5 / 5** | Medium | Console board + scripts exist, but experience is lab/PoC; no public demo; classifier may show DEGRADED; video absent |
| **Potential Impact** | **3.0 / 5** | Medium | Real ITS false-containment pain is credible; demonstrated impact is synthetic oracle + mock OF — no field metric of PacketIn saved or trips preserved |
| **Quality of the Idea** | **3.0 / 5** | Medium | Cyber–physical fusion + gated Nemotron is coherent and non-chatbot; idea space crowded by SOAR LLMs; Nemotron not shown to beat rules; gate structurally limits novel decisions |

**Composite (simple mean): ~3.0 / 5** — solid student/research PoC with unusually good honesty labeling; **not** yet differentiated enough on measured AI value or product completeness for a confident prize prediction.

### Stage One (pass/fail viability)

| Check | Status |
|-------|--------|
| Genuine track attempt (Apps/Agents) | **PASS** (intent) |
| Required Nebius + NVIDIA model use | **PASS** (code + redacted real_api) |
| Administrative completeness (public repo, video, demo URL) | **FAIL** |

---

## 9. Top three weaknesses most likely to cost a prize

1. **Mandatory artifacts incomplete** — private repo, no YouTube URL, no hosted working-demo link. Administrative DQ or auto-low Design before tech is weighed.  
2. **No demonstrated Nemotron value over the rule baseline** — 80% (n=5) vs 84% (n=25); gates prevent escalation beyond rules; Impact/Idea suffer if judges ask “why is the LLM load-bearing?”  
3. **Demo storytelling risk from stale README + synthetic/mock stack** — status table still says Nebius blocked; Lightning vs Nano mismatch; mock OF + synthetic camera invite “research wrapper” skepticism unless video leads with honesty *and* a crisp operator story.

---

## 10. Smallest changes that would materially strengthen the entry

Prioritized by impact / effort (implementation **not** done in this review):

| Priority | Change | Why it helps |
|----------|--------|--------------|
| P0 | Record & publish &lt;3 min YouTube per `docs/DEMO_VIDEO.md`; paste URL | Unlocks Design + eligibility |
| P0 | After checklist approval: make repo **public**, verify MIT visible on GitHub About | Unlocks Submission Requirements |
| P0 | Host a **credentials-free or judge-login demo URL** (Nebius Serverless Endpoint / static + API) pointing at offline+optional real path | Satisfies “working demo URL”; Design |
| P1 | Fix README status table + default model to match Nano `real_api` evidence | Removes first-impression FAIL |
| P1 | Reframe demo thesis: **“Nemotron explains and abstains under missing/conflicting evidence; rules remain authority”** — show `eval_missing_*` / conflict cases, not accuracy crown | Aligns story with evidence |
| P2 | Grow real_api held-out to **≥20** under budget, report CI / McNemar-style caution; highlight false-escalation delta if any | Strengthens Tech + Impact honesty |
| P2 | One **operator-facing** before/after vignette (rush-hour preserve vs drop) with mock OF UI pills — no fake PacketIn % | Impact storytelling without inventing metrics |
| P3 | Optional: allow Nemotron to **only de-escalate or request human**, never choose containment alone — productize the gate as the feature | Differentiates from “LLM drives SDN” hype |

---

## Limitations of this review

- Did **not** re-spend Nebius credits; relied on redacted artifacts dated 2026-10-12.  
- Did **not** run full `pytest` suite in this pass (audit claims 66 passed — **UNKNOWN** independently here).  
- Did **not** open sibling research tree or read `.env` secrets.  
- Devpost form fields (track checkbox, feedback essay) **UNKNOWN**.  
- Comparator products evolve; citations are public docs as of review time.  
- Creating this file is the only workspace write; it does not change submission eligibility by itself.

---

## Prioritized plan (for the human entrant)

1. **Eligibility pack (blocking):** video → public repo (after `PUBLIC_RELEASE_CHECKLIST`) → demo URL → Devpost fields + Nebius feedback.  
2. **Narrative alignment:** refresh README; lead with cyber–physical false-containment + gated advisory; never claim Nemotron accuracy win.  
3. **Evidence stretch (optional spend):** larger real_api held-out; keep honesty notes.  
4. **Only then** chase polish (UI motion, Serverless deploy, Ultra model experiments).

---

## Appendix A — Diff summary (hackathon delta)

Substantial new surfaces under `main...HEAD` include: `src/sdn_its/llm/*`, `src/sdn_its/utils/env.py`, hackathon datasets (`incidents/` + `eval/`), scripts (`verify_nebius_*`, `run_judge_demo`, `run_heldout_eval`, `run_hackathon_benchmark`, scans), tests (`test_nebius_llm`, `test_hackathon_agent`, `test_heldout_eval`), docs (`JUDGE_DEMO`, `DEMO_VIDEO`, `HACKATHON_CONTRIBUTIONS`, `PUBLIC_RELEASE_CHECKLIST`), and `artifacts/hackathon/*` evidence bundles.

Inherited (not invented this hackathon): detector/telemetry/camera fusion/PolicyEngine/mock OF research stack.

---

## Appendix B — Scorecard snapshot

| Gate / claim | Result |
|--------------|--------|
| Real Token Factory + Nemotron | **PASS** |
| Honesty labeling of evidence classes | **PASS** |
| Held-out disjointness | **PASS** |
| Nemotron beats rules (measured) | **FAIL** (unsupported) |
| Public repo + MIT on GitHub | **FAIL** (private) |
| YouTube &lt;3 min | **FAIL** |
| Hosted working demo URL | **FAIL / UNKNOWN** |
| README accuracy | **FAIL** (stale) |
| Prize-ready overall | **No — not yet** |
