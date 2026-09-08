# Demo video assets (captions + preview stills)

Large binaries (`*.mp4`, `*.webm`, `raw/`) are gitignored — keep them local or on Drive.

| File | Role |
|------|------|
| `iede_console_demo_en.srt` / `.ass` | English captions |
| `preview/*.jpg` | Still frames for slides / report |

Regenerate:

```powershell
.\.venv\Scripts\python.exe scripts\record_iede_demo_video.py
```
