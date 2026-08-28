#!/usr/bin/env python
"""Re-annotate prior RTSP frames with YOLO+IoU and rebuild report camera figures."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FRAMES = ROOT / "tmp" / "camera_frames"
ASSETS = ROOT / "assets" / "images" / "report"
ASSETS.mkdir(parents=True, exist_ok=True)


def main() -> None:
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from sdn_its.camera.detector import VehicleDetector

    cfg = dict(yaml.safe_load((ROOT / "configs" / "cameras.yaml").read_text(encoding="utf-8"))["detector"])
    cfg["conf"] = 0.25
    det = VehicleDetector(cfg)

    prefer = ["6dd7f379", "05c601b4", "45097883"]
    srcs = {k: next(FRAMES.glob(f"latest_cam-{k}.jpg")) for k in prefer}
    results = []
    for i, key in enumerate(prefer, 1):
        src = srcs[key]
        dest = FRAMES / f"latest_cam{i}.jpg"
        shutil.copyfile(src, dest)
        det.detect(dest, camera_id=f"cam{i}")
        out = det.detect(dest, camera_id=f"cam{i}")
        shutil.copyfile(dest, ASSETS / f"fig_cam{i}_detect.jpg")
        results.append(out)
        print(
            f"cam{i}: tracks={out.get('visible_vehicle_tracks')} "
            f"ped={out.get('pedestrian_count')} counts={out.get('counts_by_class')} "
            f"rel={out.get('context_reliability')} cold={out.get('cold_start')}"
        )

    panels = [Image.open(ASSETS / f"fig_cam{i}_detect.jpg").convert("RGB") for i in range(1, 4)]
    h = min(p.height for p in panels)
    resized = [p.resize((int(p.width * (h / p.height)), h), Image.Resampling.LANCZOS) for p in panels]
    gap = 16
    total_w = sum(p.width for p in resized) + gap * (len(resized) - 1)
    canvas = Image.new("RGB", (total_w, h + 52), (18, 18, 18))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except Exception:
        font = ImageFont.load_default()
    x = 0
    for i, p in enumerate(resized, 1):
        canvas.paste(p, (x, 44))
        draw.text(
            (x + 8, 10),
            (
                f"cam{i} LIVE frame · tracks={results[i-1].get('visible_vehicle_tracks')} · "
                f"ped={results[i-1].get('pedestrian_count')} · "
                f"rel={results[i-1].get('context_reliability')} · detector_tracker_v1"
            ),
            fill=(240, 240, 240),
            font=font,
        )
        x += p.width + gap
    canvas.save(ASSETS / "fig07_camera_tracks.png", optimize=True)
    print("collage", canvas.size)

    best = max(range(3), key=lambda i: int(results[i].get("visible_vehicle_tracks") or 0))
    hero_im = Image.open(ASSETS / f"fig_cam{best+1}_detect.jpg").convert("RGB")
    tw, th = 2880, 1800
    scale = min(tw / hero_im.width, th / hero_im.height)
    nw, nh = int(hero_im.width * scale), int(hero_im.height * scale)
    board = Image.new("RGB", (tw, th), (12, 12, 12))
    board.paste(hero_im.resize((nw, nh), Image.Resampling.LANCZOS), ((tw - nw) // 2, (th - nh) // 2))
    d2 = ImageDraw.Draw(board)
    d2.rectangle((0, 0, tw, 48), fill=(20, 20, 20))
    d2.text(
        (16, 12),
        (
            f"RTSP-captured frame + YOLOv8/IoU · tracks={results[best].get('visible_vehicle_tracks')} · "
            f"context_reliability={results[best].get('context_reliability')} · "
            "object detection (cars/moto/person) — not unusual-event AI"
        ),
        fill=(235, 235, 235),
        font=font,
    )
    board.save(ASSETS / "fig08_fusion_camera.png", optimize=True)
    print("hero cam", best + 1, board.size)


if __name__ == "__main__":
    main()
