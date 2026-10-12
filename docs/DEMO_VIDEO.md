# Demo video (&lt; 3 minutes) — production script

**Status:** Script + shot list ready. Recording/upload not automated.  
**Do not claim video published until a URL is pasted below.**

**YouTube URL:** _TBD_

## Runtime to film (safe)

```powershell
cd D:\tu_projects\sdn-its-nebius-hackathon
$env:PYTHONPATH="$PWD\src;$PWD"
# Light venv OK
python scripts/run_judge_demo.py
python scripts/run_heldout_eval.py --skip-real
# Optional blur-ready real call:
python scripts/verify_nebius_nemotron.py
.\scripts\dev.ps1   # http://127.0.0.1:8080/
```

Show **OF: mock** on the hackathon board. Never enable live switch pushes on camera.

## Shot list (target 165s)

| T | Visual | Narration |
|---|--------|-----------|
| 0:00–0:15 | Title card / README | SOLO Nebius×NVIDIA: cyber–physical investigation, not a chatbot |
| 0:15–0:35 | Console board | Synthetic telemetry + camera metadata; no private RTSP; classifier may be DEGRADED |
| 0:35–0:55 | Fixture 01 offline | Legitimate congestion → preserve/observe |
| 0:55–1:15 | Fixture 07 unsafe | Model wants temporary_drop → **gate blocks** |
| 1:15–1:40 | Terminal held-out eval | `run_heldout_eval.py --skip-real` → rule vs oracle rates; honesty note |
| 1:40–2:05 | Optional real Nebius | `verify_nebius_nemotron.py` `real_api` + model id (blur `.env`) |
| 2:05–2:30 | Benchmark honesty | Offline agreement ≠ accuracy; held-out uses oracle; no fake gains |
| 2:30–2:55 | Limitations | Mock OF, synthetic camera, private→public only after checklist |
| 2:55–3:00 | End card | Repo + docs/JUDGE_DEMO.md |

## Recording tips

- Resolution 1080p, cursor highlight on gate pills
- Do not scroll through `.env`
- Keep total under 180s
