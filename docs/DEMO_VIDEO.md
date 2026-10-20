# Demo video — JunctionTrace

**Status:** Local competition file. **Do not upload without owner approval.**  
**Public YouTube URL:** _TBD_  
**GitHub:** `*.mp4` is gitignored.

Canonical file (this is what to upload):  
`artifacts/demo_video/junctiontrace_REAL_APP_DEMO.mp4`

The older 94 s pitch (`junctiontrace_judge_demo_with_audio.mp4`) is an archive only. Do not upload it.

## Final file

| Field | Value |
|-------|--------|
| MP4 | `artifacts/demo_video/junctiontrace_REAL_APP_DEMO.mp4` |
| Capture | Headed Chrome + FFmpeg `gdigrab` of the running app at `http://127.0.0.1:8080/` |
| Duration / codecs | **75.6 s**, H.264 + AAC, 1920×1080, 30 fps |
| Voice | One speaker: Windows SAPI **Microsoft David Desktop** (~31 s) |
| QA | `artifacts/demo_video/REAL_APP_VIDEO_QA.md` |
| Rebuild | `python scripts/record_real_app_demo.py` then `python scripts/edit_real_app_demo.py` (do not iterate unless a critical QA fail) |

**Spoken names (verified):** cue 3 names **NVIDIA Nemotron** and **Nebius Token Factory**.

**On screen (actual product, not fabricated):** landing → Scenario A Safe offline tools + `preserve_rush_hour` / `deterministic planner` → Scenario B Real Nebius wait (shortened in edit, latency still shown as 21813 ms) → live `real_api` / `nemotron_conclude` / tools / `observe` vs rule `rate_limit` / gate PASS.

## Honesty (must stay true on YouTube)

- Offline planner is labeled **deterministic planner (offline)** — never live Nemotron.
- Live path shows **LIVE Nebius / real_api** and **nemotron_conclude**.
- OpenFlow is **mock**. The demo does **not** control a real traffic switch. No live PacketIn containment.
- Camera fields are **synthetic metadata**, not RTSP.
- Recommendations are advisory. The policy gate stays deterministic.

## YouTube (owner only)

Title: `JunctionTrace — investigate before you contain`  
Length: 75.6 s (under 3 minutes). Public, English. No endorsement claim.
