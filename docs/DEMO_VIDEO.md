# Demo video — JunctionTrace

**Status:** Local MP4 recorded from live UI. **Do not upload without owner approval.**

**YouTube URL:** _TBD_

## Local file

| Field | Value |
|-------|--------|
| MP4 | `artifacts/demo_video/junctiontrace_judge_demo.mp4` |
| WebM | `artifacts/demo_video/junctiontrace_judge_demo.webm` |
| Duration | **~167.8 s** (~2:48) |
| Meta | `artifacts/demo_video/junctiontrace_judge_demo_meta.json` |
| YouTube package | `artifacts/demo_video/YOUTUBE_PACKAGE.md` |

## How it was recorded

```powershell
# App running at http://127.0.0.1:8080 with server-side NEBIUS_API_KEY
python scripts/record_junctiontrace_demo.py
```

Captures actual product flow: landing → Scenario A offline → Scenario B real Nemotron → `/research` → limitations footer. Does not fabricate success; if Real mode fails, the failure is visible.

## Voiceover cues (for human narration / edit)

See `voiceover_cues` in the meta JSON / `YOUTUBE_PACKAGE.md`. Explicitly name **NVIDIA Nemotron** and **Nebius Token Factory**.

## Honesty

- Synthetic camera metadata, mock OpenFlow, advisory-only  
- Offline planner can be competitive on synthetic tests; Nemotron value is tool-mediated investigation + labeled `real_api` conclude  
- Model may use deterministic_fallback — show the trace honestly
