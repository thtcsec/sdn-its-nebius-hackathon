# Docker — research console

## Quick start

```bash
cd docker
docker compose up --build
# http://127.0.0.1:8080/
```

## Cameras (optional)

1. Keep `1.cameras.json` on the **host** (gitignored).
2. Ensure `configs/cameras.yaml` allow-list IDs match.
3. Run:

```bash
docker compose -f docker-compose.yml -f docker-compose.cameras.yml up --build
```

Mounts (base + cameras overlay):

| Host | Container |
|------|-----------|
| `1.cameras.json` | `/app/1.cameras.json` (ro) |
| `configs/` | `/app/configs` |
| `tmp/camera_frames/` | `/app/tmp/camera_frames` |
| `models/` | `/app/models` |

Preview JPEGs appear after the first successful `ffmpeg` grab (parallel, ≤3 cams).

## Notes

- Image installs **ffmpeg** + Pillow; OpenFlow remains **mock** unless you wire an external agent.
- Torch CPU wheel from PyPI makes the image large — acceptable for a research lab image.
- Do **not** bake RTSP credentials into the image; mount inventory only.
- If RTSP is LAN-only and unreachable from the bridge network, on Linux try `network_mode: host` for `controller-cameras` (not portable on Docker Desktop Windows).
