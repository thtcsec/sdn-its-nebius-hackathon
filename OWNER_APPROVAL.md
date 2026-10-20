# GO-LIVE RUNBOOK — JunctionTrace

Do **not** run any step until the matching decision is checked.  
Deadline **30 Oct 2026 10:00 AM PDT**. Keep the demo up through **15 Dec 2026**.

Application code is already on `d85fb6f`. This runbook only ships docs/packaging, then public artifacts.

**Next major milestone:** a working **public HTTPS demo URL**.  
Stop video iteration. Stop new benchmarks. Do not enable real OpenFlow.

The mock OpenFlow backend **does not** control a real traffic switch. Recommendations are advisory.

---

## Decisions (owner)

| # | Approve this | Cost / risk | [ ] |
|---|--------------|-------------|-----|
| A | **Commit** the approved-file list in `RELEASE_CANDIDATE_MANIFEST.md` (never `git add -A`) | None | |
| B | **Push** `hackathon/nebius-nvidia` | Public git history of those files | |
| C | Make the GitHub repo **public** (MIT must show on the repo page) | Irreversible | |
| D | **Pay for** a small VM and deploy HTTPS | ~$15–40 host through 15 Dec + Nebius inference | |
| E | Upload the **75.6 s** REAL_APP_DEMO MP4 to **public YouTube** | Public | |
| F | Submit Devpost + paste feedback | Binding | |

Do **not** enable real OpenFlow. App `NEBIUS_DAILY_BUDGET_USD=1.0` is **not** a Nebius hard cap.

---

## A) Commit (local)

Exact commands (copy-paste). Confirm `benchmark_offline.json` and `*.mp4` stay **out**.

```powershell
cd D:\tu_projects\sdn-its-nebius-hackathon
git status
git diff --cached --stat

# Approved paths only — do not git add -A
git add -- `
  .dockerignore .gitignore `
  CURRENT_SUBMISSION_STATUS.md OWNER_APPROVAL.md RELEASE_CANDIDATE_MANIFEST.md `
  README.md HOSTED_GO_NO_GO.md SUBMISSION_DEVPOST.md WINNING_EVIDENCE.md `
  JUDGE_ACCEPTANCE_REPORT.md FINAL_RELEASE_GATE.md `
  docs/DEMO_VIDEO.md docs/HACKATHON_CONTRIBUTIONS.md docs/NEBIUS_NVIDIA_FEEDBACK.md `
  docs/PUBLIC_RELEASE_CHECKLIST.md docs/JUDGE_HOSTING.md `
  scripts/record_junctiontrace_demo.py scripts/mux_demo_voiceover.py `
  scripts/record_real_app_demo.py scripts/edit_real_app_demo.py `
  artifacts/hackathon/docker_smoke_report.json `
  artifacts/hackathon/secret_license_scan.json `
  artifacts/hackathon/public_release_full_scan.json `
  artifacts/demo_video/media_verify.json `
  artifacts/demo_video/REAL_APP_VIDEO_QA.md `
  artifacts/demo_video/YOUTUBE_PACKAGE.md

git status
# must NOT list: artifacts/hackathon/benchmark_offline.json, *.mp4, .env, real_app_raw_*, real_app_qa/

git commit -m "Prepare JunctionTrace judge release package and honest submission docs."
```

---

## B) Push

```powershell
git push origin hackathon/nebius-nvidia
```

---

## C) Public repository

```powershell
# After docs/PUBLIC_RELEASE_CHECKLIST.md
gh repo edit thtcsec/sdn-its-nebius-hackathon --visibility public
# Confirm LICENSE (MIT) is visible on https://github.com/thtcsec/sdn-its-nebius-hackathon
```

---

## D) Single-worker HTTPS (spends money) — **this is the next milestone**

**DNS:** `A`/`AAAA` `JT_DOMAIN` → VM IP. Wait for propagation.  
**Firewall:** TCP **80** and **443** only. Do not publish 8080.  
**VM:** 1 vCPU, 1 GB RAM, Docker + Compose, Ubuntu 24.04 is enough.

```bash
# on the VM, repo at /opt/junctiontrace (hackathon/nebius-nvidia)
cd /opt/junctiontrace
cp deploy/judge/.env.example deploy/judge/.env
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# put that value in SDN_API_TOKEN
# put Token Factory key in NEBIUS_API_KEY (server-side only)
# set JT_DOMAIN=your.public.hostname
# leave NEBIUS_DAILY_BUDGET_USD=1.0  JT_RATE_LIMIT_PER_MIN=8  JT_MAX_CONCURRENT_REAL=2
# SDN_OF_BACKEND remains mock via compose — do not switch to a live controller
cd deploy/judge
docker compose up -d --build
docker compose ps
curl -fsS https://$JT_DOMAIN/api/v1/status
curl -fsS https://$JT_DOMAIN/api/v1/hackathon/capabilities
# expect hosted_demo_enforced=true of_backend_default=mock api_token_required=true
```

**External browser (not localhost, not the VM):**

```bash
curl -fsS https://$JT_DOMAIN/ | grep -F "JunctionTrace"
curl -sS -o /dev/null -w "%{http_code}\n" -X POST https://$JT_DOMAIN/api/v1/hackathon/multistep \
  -H "Content-Type: application/json" \
  -d '{"scenario_id":"scenario_rush_vs_attack","mode":"real"}'
# expect 401
```

Then from a phone/laptop off the VM: open `https://$JT_DOMAIN/`, paste `SDN_API_TOKEN`, Scenario A offline, Scenario B Real Nebius. Confirm tools, gate, `real_api` vs planner. Confirm the chip still says **OpenFlow: mock**. No live switch is attached.

**Rollback / teardown:**

```bash
cd /opt/junctiontrace/deploy/judge
docker compose logs --tail=200 app
docker compose down
# restore previous SHA then: docker compose up -d --build
# destroy quota only if abandoning: docker compose down -v
```

**Keep-alive to 15 Dec 2026:** `restart: unless-stopped`; weekly `curl https://$JT_DOMAIN/api/v1/status`.

---

## Judge access (official rules)

Rules require a **working demo URL**, free of charge, through judging. Private sites may put credentials in testing instructions.

**Do this:**

1. Devpost **Try it out** = `https://<JT_DOMAIN>/` (never `127.0.0.1`).
2. Devpost **testing instructions** (not GitHub README):  
   `Open the URL. Paste this judge token into “Judge API token”. Run Scenario A (Safe offline), then Scenario B (Real Nebius). Live calls take 10–30 seconds. OpenFlow is mock — the demo does not control a real traffic switch. Camera fields are synthetic metadata.`
3. Keep 80/443 world-reachable. Do not put Cloudflare Access / VPN in front of judges.
4. **Do not** commit the token. Rotate after judging if it leaked.

This is token-gated, free, and usable without a paid Nebius account.

---

## Spend and provider kill-switch

| Control | Reality |
|---------|---------|
| App daily $1 + 8 real calls/min + 2 concurrent | In-process only |
| Host VM | ~$5–12/month → **~$10–25** through 15 Dec |
| TLS | $0 (Caddy Let’s Encrypt) |
| Nebius if quota holds | typically ≪ $1/day; busy worst case ~$1/day **if the app quota is not bypassed** |
| If app quota is bypassed | **unbounded until the key is revoked** |

**Provider-side (do this the same day you deploy):**

1. Open [Nebius Token Factory](https://tokenfactory.nebius.com/) → **API keys**.
2. Note the key used in `deploy/judge/.env`. Enable any **budget / usage alert** the account UI offers (email/Slack). If the UI has no budget cap, treat **key revoke** as the only hard stop.
3. **Emergency:** Token Factory → API keys → **Revoke** that key. Then `docker compose down` on the VM. Spend stops when the key is dead, not when the Flask quota says so.
4. Optional: pause or power off the VM.

---

## E) YouTube

Upload **only**:

`D:\tu_projects\sdn-its-nebius-hackathon\artifacts\demo_video\junctiontrace_REAL_APP_DEMO.mp4`

Public, English, **75.6 s**, H.264/AAC. Title: `JunctionTrace — investigate before you contain`. No endorsement claim. Description: OpenFlow is mock; no live switch containment.

Paste the URL into Devpost (currently `_TBD after owner-approved YouTube upload_`).

Do **not** upload `junctiontrace_judge_demo_with_audio.mp4`.

---

## F) Devpost

Track: **Best Apps and Agents**.  
Paste `SUBMISSION_DEVPOST.md` and `docs/NEBIUS_NVIDIA_FEEDBACK.md`.  
Fill hosted URL + YouTube after D and E. Re-check https://nebiusglobalaihackathon.devpost.com/rules before submit.

---

## Agent non-actions

No commit (until A), no push, no visibility flip, no paid VM, no YouTube, no Devpost, no real OpenFlow, no keys in git.
