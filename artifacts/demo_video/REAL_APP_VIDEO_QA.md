# JunctionTrace real-app demo — visual QA

**Verdict: PASS for presentation-quality screen recording.**  
This is a headed Chrome desktop capture of the running JunctionTrace UI, not a slideshow and not Ken Burns on stills.

Old pitch file left in place: `artifacts/demo_video/junctiontrace_judge_demo_with_audio.mp4` (not overwritten).  
New file: `artifacts/demo_video/junctiontrace_REAL_APP_DEMO.mp4`

No commit, push, YouTube, Devpost, or paid deploy was performed.

---

## 1. Final encode (`ffprobe`)

| Field | Value |
| --- | --- |
| Path | `artifacts/demo_video/junctiontrace_REAL_APP_DEMO.mp4` |
| Duration | **75.567 s** (target 75–110, hard cap 180) |
| Video | H.264 High, **1920×1080**, **30 fps**, ~402 kb/s |
| Audio | AAC LC, 48 kHz, stereo, ~56 kb/s |
| Size | 4 412 070 bytes |
| Pixel format | yuv420p |
| Effects used | `trim` + `concat` hard cuts, ASS captions, AAC mix. **No zoompan, no Ken Burns, no slideshow Ken-Burns stills.** |

Raw `ffprobe` JSON: `artifacts/demo_video/real_app_qa/ffprobe.json`

---

## 2. How it was captured (proof the app was running)

- Local Flask process: `python -m api.app --host 127.0.0.1 --port 8080` (PID logged in the capture terminal).
- Browser: headed **Google Chrome**, URL `http://127.0.0.1:8080/` visible in the Chrome omnibox in every frame.
- Desktop grab: `ffmpeg -f gdigrab -framerate 30 -video_size 1920x1080 -draw_mouse 1 -i desktop`
- Playwright drove real clicks in that visible window (OS cursor is on screen).
- Capabilities at capture: `nebius_api_key_present=true`, model `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, `of_backend_default=mock`, `api_token_required=false`.

Flask access log during the recording window (no secrets):

```
20:25:22 GET  /api/v1/hackathon/capabilities  200
20:25:23 GET  /  200
20:25:23 GET  /static/junctiontrace.css  200
20:25:23 GET  /static/junctiontrace.js  200
20:25:38 POST /api/v1/hackathon/multistep  200   ← offline Scenario A
20:26:19 POST /api/v1/hackathon/multistep  200   ← live Scenario B (Nemotron)
```

The second POST returns ~21.8 s later; that latency is printed on the live board as `21813 ms` and was not fabricated.

---

## 3. Source recordings (unedited, preserved)

| File | Role |
| --- | --- |
| `artifacts/demo_video/real_app_raw_20261020T132522Z/gdigrab_source.mp4` | Primary: 88.70 s desktop capture, 1920×1080@30, cursor drawn |
| `artifacts/demo_video/real_app_raw_20261020T132522Z/playwright/*.webm` | Backup viewport recording |
| `artifacts/demo_video/real_app_raw_20261020T132522Z/capture_proof.json` | Timed click log + result excerpts |
| `artifacts/demo_video/real_app_raw_20261020T132349Z/` | Earlier headed dry-run (offline only); not used in the final |

Edit keep-windows on the gdigrab source (hard cuts only):

1. `0.15s – 42.078s` (launch, offline investigation, Real Nebius click, first ~10 s of live wait)
2. `55.016s – 88.65s` (live result paint through closing product shot)

~13 s of the middle of the live model wait was removed. The spinner is still shown; a caption states the wait was shortened. Result latency on screen remains **21813 ms**.

---

## 4. Timestamped timeline of **actual on-screen actions** (edited clock)

| Edited t | What the viewer sees |
| --- | --- |
| 0:00–0:08 | Chrome loads JunctionTrace. Product name, “Incident Investigator”, NVIDIA Nemotron / Nebius Token Factory chips, hero copy. |
| 0:08–0:12 | Scroll to scenarios; click **Safe offline**; click **Scenario A Legitimate congestion**. |
| 0:13–0:15 | Click **Investigate incident**. Loading state, then offline result. |
| 0:15–0:27 | Investigation journey tools (`retrieve_network_telemetry`, camera inspect, quality, contradictions, temporal compare). Badge **deterministic planner (offline)**. Action `preserve_rush_hour`. Gate **PASS**. Conclusion source `deterministic_fallback` (explicitly not model conclude). |
| 0:27–0:32 | Click **Real Nebius**; click **Scenario B Quiet zone + low-rate anomaly**; click **Investigate incident**. Mode hint: “Real mode calls NVIDIA Nemotron via Nebius Token Factory.” |
| 0:32–0:42 | Real loading: “Running investigation… model calls can take 10–20 seconds.” Caption: wait shortened in edit. |
| 0:43 | Hard cut to the live result as it finishes. Badge **LIVE Nebius / real_api**. Source **nemotron_conclude**. Latency 21813 ms · $0.00107 · 12072 tokens. |
| 0:45–0:58 | Tools selected during live Nemotron rounds; retrieved camera/telemetry; recommended action **observe**; rule-only **rate_limit**; gate **PASS**. |
| 0:58–1:15 | Operator board held on screen. VO + caption: OpenFlow mocked, camera synthetic, gate deterministic. Ends on the product, no animated outro. |

≥90% of the runtime is the live Chrome window. Captions are overlays on that footage, not replacement slides.

---

## 5. Voice (one speaker only)

| Item | Value |
| --- | --- |
| Engine | Windows SAPI `System.Speech.Synthesis.SpeechSynthesizer` |
| Voice ID | **Microsoft David Desktop** (en-US, male, adult) |
| Rate | `-1` (restrained) |
| Other engines | None. No Zira, no gTTS, no edge-tts. |
| Speaker count | **1** |
| Speech total | **30.88 s** (target 25–40 s) |
| Cue starts | 0.60 s, 13.86 s, 43.23 s, 66.20 s |

Spoken texts (same voice, four cues):

1. “JunctionTrace investigates traffic surges before operators disrupt a junction.”
2. “Safe offline uses a deterministic planner with real tools, never labeled as live Nemotron.”
3. **“This run calls NVIDIA Nemotron through Nebius Token Factory. Tools return evidence, then the model concludes.”**
4. “OpenFlow stays mocked. Camera metadata is synthetic. The policy gate remains deterministic.”

`ffmpeg silencedetect` on the final file shows speech at those windows (not silence): ~0.74–5.61, ~14.00–20.17, **~43.36–51.44 (Nemotron / Token Factory cue)**, ~66.32–73.82.  
Extracted cue 3 from the muxed MP4: `real_app_qa/cue2_from_final.wav`, mean −25.1 dB, peak −5.3 dB.

WAV sources: `real_app_raw_20261020T132522Z/edit_work/cue_{0,1,2,3}.wav`

No background music.

---

## 6. Visual inspection of the encoded file

Contact sheet: `artifacts/demo_video/real_app_qa/contact_sheet.jpg`  
Per-frame stills every 5 s: `artifacts/demo_video/real_app_qa/contact/frame_*.jpg`

Checked by opening the encoded frames, not by duration/codec alone:

- Chrome window chrome, `127.0.0.1:8080`, Windows taskbar clock advancing 20:25 → 20:26.
- OS mouse pointer visible on landing and scenario clicks.
- Offline vs live badges are the real product labels.
- Live board shows `observe` vs rule-only `rate_limit` at the same time as `nemotron_conclude`.
- Browser viewport scale is constant 1920×1080; no slow zoom, no pan, no PowerPoint wipe.

### Static holds longer than 4 seconds (real UI, not stills-as-video)

| Edited span | What is held | Notes |
| --- | --- | --- |
| ~0:00–0:08 | Landing / hero | Real page; cursor later moves. |
| ~0:16–0:26 | Offline result board | Real DOM; some scroll between timeline and result. |
| ~0:33–0:42 | Live loading skeleton | Honest wait remainder after the cut. |
| ~0:58–1:15 | Live operator board | Scene D requirement: keep the result visible. Captions/VO change; no camera move. |

These are dwells on a live page, not Ken Burns. x264 skip% is high because the UI is mostly stationary — Ken Burns would encode continuous motion.

---

## 7. Labels, secrets, honesty

| Check | Result |
| --- | --- |
| Offline labeled live Nemotron? | **No.** Badge: `deterministic planner (offline)`; source `deterministic_fallback`. |
| Live labeled correctly? | **Yes.** `LIVE Nebius / real_api` + `nemotron_conclude`. This was a real Token Factory call, not a replay. |
| Replay mis-sold as live? | N/A — live path was used. |
| Wait time misrepresented? | Caption on the spinner: “Live model call in progress — wait shortened in edit.” On-screen latency still 21813 ms. |
| API keys / tokens in frames? | **None.** URL is localhost. Judge token field is empty. No `sk-` / bearer strings. |
| Cost line | `$0.00107` estimated usage — not a credential. |
| OpenFlow / camera | On-screen: `OF mock`, `synthetic camera metadata`. VO repeats the same. |

---

## 8. Known limitations of this recording (not fail-closed)

- Recorded against **local Flask** on `:8080`, not the Docker/Caddy judge stack. It is the same JunctionTrace product UI.
- Windows taskbar remains visible (desktop capture).
- The empty judge-token row is visible because product CSS `.mode-row { display:flex }` can override `[hidden]`. Real UI, not a fake chrome.
- Scene D holds the operator result without further clicks (~15 s) so VO can land. That is a dwell, not a slideshow.

---

## 9. Release gate for *this* video

| Criterion | Result |
| --- | --- |
| ≥90% genuine recorded app UI | **PASS** |
| No screenshot Ken Burns / fake UI | **PASS** |
| 75–110 s, H.264/AAC, 1080p30 | **PASS** (75.6 s) |
| One English voice; names NVIDIA Nemotron and Nebius Token Factory | **PASS** |
| Live `real_api` / `nemotron_conclude` / `observe` vs `rate_limit` / gate actually on screen | **PASS** |
| Old 94 s pitch not overwritten | **PASS** |
| Slideshow? | **No — FAIL condition not met** |

This file is independently reviewable. It is **not** a substitute for the remaining competition blockers (public repo, hosted HTTPS URL, YouTube upload, Devpost) which still require owner approval.

---

## 10. Final release review (2026-10-20, stop video iteration)

Re-inspected the encoded 75.6 s file (contact frames at 0:20, 0:45, 0:55, 1:00, 1:10). **Keep this MP4.** No critical QA fail.

| Check | Result |
| --- | --- |
| Tools readable | **PASS** — retrieve_network_telemetry, inspect_camera_metadata, compare_temporal_windows (and offline extra tools) |
| Model conclude readable | **PASS** — `nemotron_conclude` + action `observe` |
| Gate readable | **PASS** — `gate PASS`; “No policy clamp” |
| One narrator | **PASS** — Microsoft David Desktop only |
| Tokens in frames | **PASS** — none; empty judge-token field is not a secret |
| LIVE vs offline labels | **PASS** — planner vs `LIVE Nebius / real_api` |
| Mock OF ≠ real switch | **PASS** — `OF mock`, “No live switch containment is performed”, closing VO |

Non-critical (do not rebuild): Windows taskbar, empty token row, captions overlay the lower board at ~0:45, Scene D dwell.

**Next milestone:** public HTTPS demo URL. Not another video. Not another benchmark.
