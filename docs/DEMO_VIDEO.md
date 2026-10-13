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
| 0:00–0:15 | Title card | Product story: a surge is not always an attack — investigate physical context |
| 0:15–0:40 | Console · scenario rush | Multi-step: tools inspect camera metadata → contradiction → preserve/observe |
| 0:40–1:05 | Console · missing camera | Tools flag insufficient evidence → gate blocks containment → observe |
| 1:05–1:25 | Trace panel | DETECT → tools → REASON → POLICY GATE → AUDIT (mock OF) |
| 1:25–1:50 | Terminal ablation | `run_ablation_study.py --skip-real` — A/B/C/D on same held-out inputs |
| 1:50–2:15 | Optional real Nebius | `verify_nebius_nemotron.py` or multistep `--real` (blur `.env`) |
| 2:15–2:40 | Honesty | Offline planner ≠ live Nemotron; camera = synthetic metadata; no fake gains |
| 2:40–2:55 | Limitations | Mock OF; public repo/video still require owner approval |
| 2:55–3:00 | End card | `docs/JUDGE_DEMO.md` + `COMPETITION_DELTA_REPORT.md` |

## Recording tips

- Resolution 1080p, cursor highlight on gate pills
- Do not scroll through `.env`
- Keep total under 180s
