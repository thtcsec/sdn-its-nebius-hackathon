# Slide screenshots — usage guide

Captured: 2026-08-28 ~22:36 (local). Folder: `assets/images/slides/`  
Prefer `*.jpg` for Canvas/PowerPoint (smaller). PNG kept as masters.

Live camera state at capture: `live_rtsp=3`, `source=detector_tracker_v1`, OF=`mock` (Windows).

## Which file → which slide

| File | Put on | Caption / what to say |
|------|--------|------------------------|
| `slide_01_console_overview.jpg` | Results / Demo overview | Ops console with evidence strip (MODEL / OF·mock / NET). Shows the research UI, not a SOC claim. |
| `slide_02_live_cameras.jpg` | Camera context slide | Live RTSP stills + YOLO tracks feeding fusion. Object detection = physical context support, **not** accident AI / traffic census. |
| `slide_03_fusion_rush_preserve.jpg` | Safety-aware fusion | Rush physical context + distributed sources → `preserve_rush_hour` (false-positive avoidance policy). |
| `slide_04_ddos_containment.jpg` | Mitigation demo | PacketIn/DDoS inject → temporary containment intent. On Windows this is **mock** OpenFlow (in-memory), not switch-verified. |
| `slide_05_re_chart_ddos.jpg` | Detection signal | Reconstruction-error chart rising under flood inject — model decision path. |
| `slide_06_rush_hour_network.jpg` | Honesty / GT-PRED | Rush-hour network label path; keep GT/PRED/MATCH visible if shown. |

## Camera IDs used (local allow-list)

Configured in gitignored `configs/cameras.local.yaml` (UI labels stay `cam1..cam3`):

1. `1cea682d-…` → `caxphuhuu179.ddns.net:554` (primary)
2. `6dd7f379-…` → `hf6095z95vw.sn.mynetname.net:559`
3. `05c601b4-…` → `hf6095z95vw.sn.mynetname.net:559`

Inventory probe found **7/15** streams ffprobe-OK; default `first_n` previously picked dead DDNS hosts. Repo now prefers DNS-reachable hosts in `first_n`; local YAML pins the three demo cams.

## Do not claim on slides

- Live camera ≠ labeled-video FP reduction proof  
- Mock OF ≠ Mininet Experiment A switch evidence  
- Track counts ≠ vehicles/hour  
