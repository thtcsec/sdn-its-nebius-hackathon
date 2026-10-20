# SUBMISSION READY — JunctionTrace

**Competition:** Nebius × NVIDIA Global AI Hackathon · Best Apps and Agents  
**Deadline:** Fri **30 Oct 2026 10:00am PT** ([official rules](https://nebiusglobalaihackathon.devpost.com/rules))  
**Branch:** `hackathon/nebius-nvidia`  
**Repo:** https://github.com/thtcsec/sdn-its-nebius-hackathon — **PRIVATE**  
**License:** MIT (`LICENSE`) — must be visible on the GitHub page after the owner makes the repo public

This file is the current status authority. Older gates remain dated audits.

## Release identity

| Item | Value |
|---|---|
| **Current release-docs SHA** | `bb95d5c8403694b3ec846770d7544c681fc43738` |
| **Application / product tree** | `47dc614` — `api/`, `dashboard/`, `src/` unchanged in this packaging pass |
| **CI workflow** | `.github/workflows/hackathon-light.yml` on `hackathon/nebius-nvidia` only |
| **CI on `bb95d5c`** | https://github.com/thtcsec/sdn-its-nebius-hackathon/actions/runs/39459887568 — **success**, 78 passed, `NEBIUS_API_KEY` unset |

CI is credential-free. **CI did not run live Nemotron.**

## Canonical demo (local only)

| Item | Value |
|---|---|
| File | `artifacts/demo_video/junctiontrace_REAL_APP_DEMO.mp4` |
| Git | **gitignored** — not on GitHub |
| Duration / codecs | **75.567 s**, H.264 1920×1080@30 + AAC |
| SHA-256 | `59073CF5B64E3624EB40BA9F0DD4218A1AC62EEEB468139C8E822A6DB81736B9` |
| Voice | One English SAPI voice; names **NVIDIA Nemotron** and **Nebius Token Factory** |
| Do not upload | `junctiontrace_judge_demo_with_audio.mp4` (94 s pitch) |
| Public YouTube URL | **MISSING** |

## Functional judge instructions

Local (no torch):

```powershell
pip install "python-dotenv>=1.0" "requests>=2.31" "pyyaml>=6" "Flask>=2.3"
$env:PYTHONPATH="$PWD\src;$PWD"
python -m api.app --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080/`. Scenario A = **Safe offline** deterministic planner. Scenario B = **Real Nebius** only with a server-side `NEBIUS_API_KEY`. Hosted package: `docs/JUDGE_HOSTING.md`. Token-gated; unauthorized real → **401**. OpenFlow stays **mock**.

## Honest limitations (do not collapse)

- Offline deterministic planner is **not** Nebius.
- Real inference uses **NVIDIA Nemotron** through **Nebius Token Factory**.
- OpenFlow is **MOCK**. No evidence of controlling a real traffic switch.
- Camera data is **synthetic metadata**.
- Offline ≈**92%** (n=25 planner) is **not** live Nemotron accuracy.
- Blind live C: **n=4, 3/4**, ~17.2 s, fallback 0.25 — keep the denominators.
- App `NEBIUS_DAILY_BUDGET_USD` is **not** a provider-side hard spending cap. Revoke the Token Factory key to stop spend.

## External URLs

| Artifact | Status |
|---|---|
| Public GitHub repo | **MISSING** (still private) |
| Working public HTTPS demo URL | **MISSING** |
| Public YouTube ≤ 3 min | **MISSING** |
| Devpost submit | **MISSING** |

## Remaining owner actions

1. Re-read `docs/PUBLIC_RELEASE_CHECKLIST.md`, then make the repo **public** (owner only).  
2. Deploy HTTPS demo **or** use any rules-permitted private-demo credential path (`docs/JUDGE_HOSTING.md`).  
3. Upload **only** `junctiontrace_REAL_APP_DEMO.mp4` to public YouTube; paste URL.  
4. Paste `SUBMISSION_DEVPOST.md` + `docs/NEBIUS_NVIDIA_FEEDBACK.md` and submit.  
5. Same day as any deploy: enable Token Factory usage alerts; keep **key revoke** as the hard stop.  
6. Do **not** enable real OpenFlow.

## Overall status

**ENGINEERING READY** for local/Docker judge reproduction.  
**Competition submission: BLOCKED** until public repo, hosted demo URL, YouTube, and Devpost.
