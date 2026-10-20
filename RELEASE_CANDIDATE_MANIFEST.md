# Release candidate manifest — JunctionTrace

**Verified:** 2026-10-20  
**Branch:** `hackathon/nebius-nvidia`  
**Remote / local tip (application code):** `d85fb6fb542f6fb22bc5fc20667377739e279396`  
**Security-fix ancestry:** `000354720adb422659e5a11cbf9603f49951bcbd`  
**CI tested SHA:** `d85fb6f` — https://github.com/thtcsec/sdn-its-nebius-hackathon/actions/runs/39258073978 — **78 passed**, credential-free (`NEBIUS_API_KEY` unset). **CI did not run live Nemotron.**

Local light pytest: **78 passed** (credential-free). Local Docker smoke this session: **7/7** (`docker_smoke_report.json`, 2026-10-20T14:03Z).

---

## Phase 1 freeze

| Question | Answer |
|----------|--------|
| Dirty `api/` / `dashboard/` / `src/` vs remote? | **None.** Product code matches `origin/hackathon/nebius-nvidia` @ `d85fb6f`. |
| What reproduces the recorded demo UI? | `api/`, `dashboard/`, `src/sdn_its/llm/`, `datasets/hackathon/`, `docker/Dockerfile.judge`, `deploy/judge/` — all already on the tip. |
| Unrelated dirty file | `artifacts/hackathon/benchmark_offline.json` — timestamp/latency rerun only. **Leave unstaged.** |

### Include in a later owner commit (docs + packaging)

Copy-paste list is in `OWNER_APPROVAL.md` §A. Summary:

- `CURRENT_SUBMISSION_STATUS.md`
- `OWNER_APPROVAL.md`
- `RELEASE_CANDIDATE_MANIFEST.md` (this file)
- `README.md`
- `HOSTED_GO_NO_GO.md`
- `SUBMISSION_DEVPOST.md`
- `WINNING_EVIDENCE.md`
- `JUDGE_ACCEPTANCE_REPORT.md` (historical labels only)
- `FINAL_RELEASE_GATE.md` (historical labels only)
- `docs/DEMO_VIDEO.md`
- `docs/HACKATHON_CONTRIBUTIONS.md`
- `docs/NEBIUS_NVIDIA_FEEDBACK.md`
- `docs/PUBLIC_RELEASE_CHECKLIST.md`
- `docs/JUDGE_HOSTING.md`
- `.dockerignore`
- `.gitignore` (ignore raw recordings + smoke token file)
- `scripts/record_junctiontrace_demo.py`
- `scripts/mux_demo_voiceover.py`
- `scripts/record_real_app_demo.py`
- `scripts/edit_real_app_demo.py`
- `artifacts/hackathon/docker_smoke_report.json`
- `artifacts/hackathon/secret_license_scan.json`
- `artifacts/hackathon/public_release_full_scan.json`
- `artifacts/demo_video/media_verify.json`
- `artifacts/demo_video/REAL_APP_VIDEO_QA.md`
- `artifacts/demo_video/YOUTUBE_PACKAGE.md`

### Do not add

- `artifacts/hackathon/benchmark_offline.json` (unrelated local rerun)
- `artifacts/demo_video/*.mp4` / `*.wav` / `real_app_raw_*` / `real_app_qa/` (gitignored; local only)
- `deploy/judge/.env` / `.env.smoke` / `.tmp_judge_token.txt`
- Any `.env`, keys, or paid-host URLs
- Product `src/`, `api/`, `dashboard/` (already clean on `d85fb6f`)

Do **not** `git add -A`.

---

## Judge agent evaluation (existing evidence + this rehearsal)

Loop is **tool-mediated**, not a static LLM dump:

1. Incident + uncertainties  
2. Tool selection (`retrieve_network_telemetry`, `inspect_camera_metadata`, `check_physical_evidence_quality`, …)  
3. Tool execution returns evidence  
4. Conclude (`pre_gate_source=nemotron_conclude` **or** `deterministic_fallback` / planner)  
5. Deterministic policy gate  
6. Operator explanation  

| Evidence | Result |
|----------|--------|
| Matched live (`matched_nemotron_proof.json`) | `evidence_class=real_api`; tools chosen in-loop; mixed `nemotron_conclude` vs `deterministic_fallback` |
| Live product e2e (`e2e_product_report.json`) | Scenario B: `ec=real_api` tools `retrieve_network_telemetry`, `inspect_camera_metadata`, `compare_temporal_windows` |
| Blind live C | **n=4, 3/4**, ~**17.2 s**, fallback **0.25** — not real-world accuracy |
| Offline planner D | ≈**92%** on n=25 — **not** Nemotron accuracy |
| Paired gate C→D | **No accuracy win** from the gate on matched live n=4; adversarial synthetics prove enforcement |
| This Docker UI | Scenario A offline → `preserve_rush_hour`; Scenario C stale camera → `observe` vs rule-only `rate_limit` |

OpenFlow **mock**. Camera **synthetic metadata**. Latency is advisory seconds, not control-loop ms.

---

## Local Docker rehearsal (2026-10-20)

Script: `python scripts/smoke_judge_docker.py` → `artifacts/hackathon/docker_smoke_report.json` **7/7**.

Additional live stack @ `http://127.0.0.1:18080/` (torn down after rehearsal):

| Check | Result |
|-------|--------|
| Fresh build + compose boot | PASS |
| Landing page (browser) | PASS — JunctionTrace hero, 4 scenarios |
| Offline demo (browser + API) | PASS — tools + gate + `preserve_rush_hour` / `observe` |
| Unauthorized real | **401** |
| Placeholder token | container **refuses to start** |
| Hosted mock OF | `of_backend_default=mock`, `hosted_demo_enforced=true` |
| Quota SQLite restart | volume hash changed and survived restart |
| Rate limit | 9th/10th real-mode calls **429** (`JT_RATE_LIMIT_PER_MIN=8`) |
| Legacy `/api/v1/hackathon/investigate` + `/run` | **410** |
| Secrets in image | no `.env` in `/app`; tokens via env_file only |
| Caddy TLS smoke | https://localhost:18443 **200** (internal cert) |
| No RTSP / checkpoints required | PASS |

This is **not** a public host.

---

## Media

| Item | Status |
|------|--------|
| **Canonical MP4** | `artifacts/demo_video/junctiontrace_REAL_APP_DEMO.mp4` |
| Duration / codecs | **75.6 s**, h264 + aac, 1920×1080@30 |
| Capture | Headed Chrome + FFmpeg `gdigrab` of the running JunctionTrace UI |
| Voice | One SAPI speaker: **Microsoft David Desktop** |
| Spoken names | Cue names **NVIDIA Nemotron** and **Nebius Token Factory** |
| Product footage | landing → offline planner/`preserve_rush_hour` → live `real_api`/`nemotron_conclude`/`observe` vs `rate_limit`/gate PASS |
| OpenFlow | **mock** on screen and in VO — not a real traffic switch |
| QA | `artifacts/demo_video/REAL_APP_VIDEO_QA.md` — **PASS**, keep this file |
| Archive (do not upload) | `junctiontrace_judge_demo_with_audio.mp4` (94 s) |
| GitHub / YouTube | **not present** |

**Next milestone:** public HTTPS demo URL (`docs/JUDGE_HOSTING.md`). Not another video.

### Exact staging (do not `git add -A`)

See `OWNER_APPROVAL.md` §1–2. **Exclude** `artifacts/hackathon/benchmark_offline.json`. Application `src/`, `api/`, `dashboard/` are **clean vs `d85fb6f`** — that is the UI in the video.

---

## Verdicts

| Gate | Verdict |
|------|---------|
| Engineering / host package | **GO** |
| Competition submission | **NO-GO / BLOCKED** until public repo, hosted demo URL, YouTube, Devpost |

Owner next steps: `OWNER_APPROVAL.md`.
