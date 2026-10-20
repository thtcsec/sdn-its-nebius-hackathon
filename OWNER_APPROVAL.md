# GO-LIVE RUNBOOK — JunctionTrace

**Status authority:** [`SUBMISSION_READY.md`](SUBMISSION_READY.md)  
Deadline **30 Oct 2026 10:00 AM PDT**. Keep any hosted demo up through **15 Dec 2026**.

Application code is on `47dc614`. This runbook is **owner-only remaining actions**. Do **not** treat the docs already on `origin/hackathon/nebius-nvidia` as still needing a first commit.

The mock OpenFlow backend **does not** control a real traffic switch. Recommendations are advisory.

## Remaining owner decisions

| # | Approve this | Cost / risk |
|---|--------------|-------------|
| C | Make the GitHub repo **public** (MIT must show on the repo page) | Irreversible |
| D | **Pay for** a small VM and deploy HTTPS | host through 15 Dec + Nebius inference |
| E | Upload the **75.6 s** REAL_APP_DEMO MP4 to **public YouTube** | Public |
| F | Submit Devpost + paste feedback | Binding |

Do **not** enable real OpenFlow. App `NEBIUS_DAILY_BUDGET_USD=1.0` is **not** a Nebius hard cap.

## C) Public repository

After `docs/PUBLIC_RELEASE_CHECKLIST.md`:

```powershell
gh repo edit thtcsec/sdn-its-nebius-hackathon --visibility public
```

## D) Single-worker HTTPS (spends money)

See `docs/JUDGE_HOSTING.md`. Firewall TCP 80/443 only. `SDN_OF_BACKEND` remains mock. Unauthorized real → 401. Provider kill-switch is **Token Factory key revoke**, not the app quota.

## E) YouTube

Upload **only** `artifacts/demo_video/junctiontrace_REAL_APP_DEMO.mp4`.  
Do **not** upload `junctiontrace_judge_demo_with_audio.mp4`.

## F) Devpost

Track: **Best Apps and Agents**. Paste `SUBMISSION_DEVPOST.md` and `docs/NEBIUS_NVIDIA_FEEDBACK.md`.

## Agent non-actions

No visibility flip, no paid VM, no YouTube, no Devpost, no real OpenFlow, no keys in git.
