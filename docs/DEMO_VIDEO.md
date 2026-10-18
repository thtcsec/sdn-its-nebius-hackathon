# Demo video (&lt; 3 minutes) — JunctionTrace storyboard

**Status:** Storyboard ready. Recording/upload not automated.  
**Do not claim video published until a URL is pasted below.**

**YouTube URL:** _TBD — owner approval required before upload_

## Runtime to film (safe)

```powershell
cd D:\tu_projects\sdn-its-nebius-hackathon
$env:PYTHONPATH="$PWD\src;$PWD"
.\scripts\dev.ps1   # http://127.0.0.1:8080/
# Optional: set NEBIUS_API_KEY server-side for one real investigation
```

Show **OF: mock**. Never enable live switch pushes. Never scroll through `.env`.

## Shot list (target ≤165s)

| T | Visual | Narration |
|---|--------|-----------|
| 0:00–0:12 | Landing `/` first viewport | **JunctionTrace** — a traffic surge is not always an attack; investigate physical context before disruption |
| 0:12–0:35 | Scenario A · Safe offline | Legitimate congestion: tools see rush-hour queue → avoid pointless containment; label = deterministic planner |
| 0:35–1:05 | Scenario B · Real Nebius | Quiet zone + low-rate anomaly: rule-only may rate-limit; Nemotron may observe if evidence is thin — show full trace + model variability |
| 1:05–1:25 | Timeline + badges | Tools → retrieve → conclude → gate → audit; `LIVE Nebius / real_api` vs offline never confused |
| 1:25–1:45 | Gate + OF mock | Policy gate + mock OpenFlow; no live containment |
| 1:45–2:05 | AI vs baseline | Side-by-side rule-only vs investigation; honest that offline planner often matches or beats model on held-out |
| 2:05–2:25 | `/research` | Pre-existing IEDE research console preserved |
| 2:25–2:45 | Security honesty | Server token, daily budget, rate limits; keys never in browser |
| 2:45–3:00 | End card | Limitations + repo SHA; hosted URL / public / Devpost need owner approval |

## Recording tips

- 1080p; keep Scenario B wording honest (uncertainty, not “credible cyberattack”)
- If Real mode is budget-blocked, film that error honestly — do not splice a fake PASS
- Total under 180s
