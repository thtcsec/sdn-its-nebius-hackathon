# CURRENT SUBMISSION STATUS — JunctionTrace

**Verified UTC:** 2026-10-20 (release rehearsal)  
**Branch:** `hackathon/nebius-nvidia`  
**Repo visibility:** **PRIVATE** (`thtcsec/sdn-its-nebius-hackathon`)  
**Official rules:** [Nebius × NVIDIA Global AI Hackathon — Official Rules](https://nebiusglobalaihackathon.devpost.com/rules) (Submission Period ends Fri Oct 30, 2026 10:00am PT)

---

## Verdicts (do not conflate)

| Gate | Verdict | Meaning |
|------|---------|---------|
| **Engineering / hosted security package** | **GO** | Single-worker, token-gated, mock-OF judge package is ready to *deploy when owner approves*. Local Docker smoke ≠ public host. |
| **Competition / Devpost submission** | **BLOCKED** | Mandatory public artifacts missing. Engineering GO does **not** equal submission-ready. |

---

## Verified SHAs (this audit)

| Role | Full SHA | Short |
|------|----------|-------|
| **Branch tip** (local HEAD = `origin/hackathon/nebius-nvidia`) | `d85fb6fb542f6fb22bc5fc20667377739e279396` | `d85fb6f` |
| **Security-fix commit** (placeholder judge tokens rejected) | `000354720adb422659e5a11cbf9603f49951bcbd` | `0003547` |
| Tip is **tip = fix + docs commit** that records the fix | tip message: *Record placeholder-token fix SHA and green CI in HOSTED_GO_NO_GO.* | |

**Do not treat `0003547` as the current tip.** Tip is `d85fb6f`. The fix lives in ancestry; tip CI re-ran the same light suite on `d85fb6f`.

---

## CI (branch-specific, credential-free)

| Item | Value |
|------|-------|
| Workflow | `.github/workflows/hackathon-light.yml` — triggers on `push`/`pull_request` to **`hackathon/nebius-nvidia` only** |
| Latest tip run | [39258073978](https://github.com/thtcsec/sdn-its-nebius-hackathon/actions/runs/39258073978) — **success** |
| Tested SHA | `d85fb6fb542f6fb22bc5fc20667377739e279396` |
| Result | **78 passed** in ~1.64s |
| Prior fix run | [39257990678](https://github.com/thtcsec/sdn-its-nebius-hackathon/actions/runs/39257990678) on `0003547` — success |
| Env in CI | Nebius key left unset in the workflow — **no live Nebius / Nemotron inference in CI** |
| Scope | Offline planner, schema/security, product UI, multi-step unit paths — **not** Token Factory `real_api` |

Older reports that claim “no CI” inspected an earlier tip (e.g. `JUDGE_ACCEPTANCE_REPORT.md` at `dcc7ac0`, 2026-10-13) before `hackathon-light` existed. Those historical claims stay labeled by SHA; they are **not** the current CI state.

---

## Evaluation snapshots (keep separate)

| Study | Artifact | What it is | Honest ceiling |
|-------|----------|------------|----------------|
| Offline ablation | `artifacts/hackathon/ablation_offline.json` | Deterministic planner + tools; arm D ≈ **92%** on n=25 | **Not** Nemotron accuracy |
| Matched live proof | `artifacts/hackathon/matched_nemotron_proof.json` / `WINNING_EVIDENCE.md` | Small curated live B/C/D | Small-n; separate from blind |
| Paired gate study | `artifacts/hackathon/paired_gate_study.json` / `FINAL_RELEASE_GATE.md` | C freeze → D gate replay | **No C→D accuracy win** on matched live sample; adversarial synthetic proves enforcement |
| Blind red-team | `artifacts/hackathon/blind_redteam_eval.json` (ts `2026-10-13`) | Arms A/B/C/D; OF **mock**; camera **synthetic_metadata_only** | Live C: **n=4**, **3/4** vs assumption oracle, mean latency **~17.2 s**, fallback **0.25**, `real_api_rate` 0.75 |

Blind live C summary (from JSON, not marketing copy):

- `correct_vs_oracle_rate`: 0.75 (3/4)
- `mean_latency_ms`: ≈ 17210
- `fallback_rate`: 0.25
- `nemotron_conclude_rate`: 0.75

---

## Demo video (local vs public)

| Check | Status |
|-------|--------|
| Canonical local MP4 | **Present:** `artifacts/demo_video/junctiontrace_REAL_APP_DEMO.mp4` |
| Duration / codecs | **75.6 s** (&lt; 3 min); **h264** + **aac**, 1920×1080@30 |
| Capture | Real headed Chrome + FFmpeg desktop grab of the running UI (not a slideshow) |
| Verbal naming | One SAPI voice (**Microsoft David Desktop**) names **NVIDIA Nemotron** and **Nebius Token Factory** |
| Labels | Offline = `deterministic planner`; live = `LIVE Nebius / real_api` + `nemotron_conclude` |
| OpenFlow | On-screen **OF mock**; VO: no live switch containment |
| On GitHub | **No** — `*.mp4` gitignored; QA markdown is trackable |
| Public YouTube URL | **Missing** — TBD; do not invent |
| Archive (do not upload) | `junctiontrace_judge_demo_with_audio.mp4` (94 s pitch) |

---

## Official submission blockers (rules-verified)

From Official Rules § Submission Requirements (Best Apps and Agents track):

1. **Public** GitHub/GitLab/Bitbucket repo with **visible open-source license** → currently **private** (MIT `LICENSE` present locally).
2. **Working demo URL** (hosted app / test build) → **not deployed**; loopback / local Docker only. Engineering GO ≠ hosted URL.
3. **Public YouTube ≤ 3 minutes** → canonical local MP4 is `junctiontrace_REAL_APP_DEMO.mp4` (75.6 s); **URL absent**.
4. Complete Devpost fields + **Nebius/NVIDIA feedback** → drafts ready (`SUBMISSION_DEVPOST.md`, `docs/NEBIUS_NVIDIA_FEEDBACK.md`); **not submitted**.
5. Runtime call to Nebius Token Factory / NVIDIA model → **capability exists** with server-side key; not proven by CI.

**Application daily quota ≠ Nebius provider hard spend cap.** Disclose that.

---

## Historical reports (preserve; do not rewrite their NO-GOs)

| Document | SHA / date examined | Historical verdict | Relation to tip `d85fb6f` |
|----------|---------------------|--------------------|---------------------------|
| `JUDGE_ACCEPTANCE_REPORT.md` | `dcc7ac0` @ 2026-10-13 | **NO-GO** submission; CI absent | Superseded on CI/video-file facts; eligibility blockers still hold |
| `FINAL_RELEASE_GATE.md` | freeze tip `e332cc6` / study `5fc3df2` | Engineering freeze of paired-gate work | Evidence honesty still valid; SHA is not tip |
| `WINNING_EVIDENCE.md` | live proof `06b8bd7` | Matched live value case | Keep; small-n; not blind study |
| `HOSTED_GO_NO_GO.md` | originally recorded fix `0003547` | Engineering **GO** | Tip now `d85fb6f`; tip CI 39258073978 |

---

## Owner actions still required (explicit non-actions for agents)

- [ ] Make repository **public** (owner) after `docs/PUBLIC_RELEASE_CHECKLIST.md`
- [ ] Deploy hosted demo URL (owner; may cost money) **or** use any rules-permitted private demo credentials path
- [ ] Upload YouTube (owner) from `junctiontrace_REAL_APP_DEMO.mp4` only; paste URL into Devpost
- [ ] **Next milestone:** working public HTTPS demo URL (`docs/JUDGE_HOSTING.md`) — not another video or benchmark
- [ ] Paste feedback + Devpost fields and **submit** (owner)
- [ ] Do **not** treat app daily quota as provider hard cap in marketing

This file is the **current** status authority. Older gates remain as dated audits.
