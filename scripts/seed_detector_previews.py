#!/usr/bin/env python
"""Seed cam1..cam3 previews from prior RTSP grabs + re-run YOLO annotate for report shots."""

from __future__ import annotations

import shutil
import time
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
    from sdn_its.camera.detector import get_detector

    cfg = yaml.safe_load((ROOT / "configs" / "cameras.yaml").read_text(encoding="utf-8"))["detector"]
    det = get_detector(cfg)
    print("detector", det.status())

    prefer = ["6dd7f379", "05c601b4", "45097883"]
    srcs = list(FRAMES.glob("latest_cam-*.jpg"))
    ordered: list[Path] = []
    for key in prefer:
        for p in srcs:
            if key in p.name and p not in ordered:
                ordered.append(p)
    for p in srcs:
        if p not in ordered:
            ordered.append(p)
    if len(ordered) < 1:
        raise SystemExit("no inventory frames in tmp/camera_frames")

    results = []
    for i, src in enumerate(ordered[:3], 1):
        dest = FRAMES / f"latest_cam{i}.jpg"
        shutil.copyfile(src, dest)
        out = det.detect(dest, camera_id=f"cam{i}")
        # detector writes annotated JPEG in-place when annotate_preview=true
        asset = ASSETS / f"fig_cam{i}_detect.jpg"
        shutil.copyfile(dest, asset)
        im = Image.open(dest)
        results.append(
            {
                "cam": f"cam{i}",
                "tracks": out.get("visible_vehicle_tracks"),
                "rel": out.get("context_reliability"),
                "device": out.get("device"),
                "size": im.size,
                "path": asset.name,
            }
        )
        print(
            f"cam{i}: tracks={out.get('visible_vehicle_tracks')} "
            f"rel={out.get('context_reliability')} "
            f"{im.size[0]}x{im.size[1]} -> {asset.name}"
        )

    # Collage for report Fig 8
    panels = [Image.open(ASSETS / f"fig_cam{i}_detect.jpg").convert("RGB") for i in range(1, len(results) + 1)]
    # normalize heights
    h = min(p.height for p in panels)
    resized = []
    for p in panels:
        w = int(p.width * (h / p.height))
        resized.append(p.resize((w, h), Image.Resampling.LANCZOS))
    gap = 16
    total_w = sum(p.width for p in resized) + gap * (len(resized) - 1)
    canvas = Image.new("RGB", (total_w, h + 48), (18, 18, 18))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except Exception:
        font = ImageFont.load_default()
    x = 0
    for i, p in enumerate(resized, 1):
        canvas.paste(p, (x, 40))
        label = f"cam{i} · detector_tracker_v1 · tracks={results[i-1]['tracks']} · rel={results[i-1]['rel']}"
        draw.text((x + 8, 10), label, fill=(240, 240, 240), font=font)
        x += p.width + gap
    collage = ASSETS / "fig07_camera_tracks.png"
    # save as high-res PNG
    canvas.save(collage, optimize=True)
    print(f"collage -> {collage} {canvas.size}")

    # Single hero detect frame (busy junction) for fusion companion
    hero = ASSETS / "fig08_fusion_camera.png"
    # Use cam1 detect + caption bar
    hero_im = Image.open(ASSETS / "fig_cam1_detect.jpg").convert("RGB")
    # fit landscape ~16:10 canvas with side padding dark
    target_w, target_h = 2880, 1800
    scale = min(target_w / hero_im.width, target_h / hero_im.height)
    nw, nh = int(hero_im.width * scale), int(hero_im.height * scale)
    hero_r = hero_im.resize((nw, nh), Image.Resampling.LANCZOS)
    board = Image.new("RGB", (target_w, target_h), (12, 12, 12))
    board.paste(hero_r, ((target_w - nw) // 2, (target_h - nh) // 2))
    d2 = ImageDraw.Draw(board)
    d2.rectangle((0, 0, target_w, 44), fill=(20, 20, 20))
    d2.text(
        (16, 10),
        f"Live-captured RTSP frame · YOLO+IoU annotate · tracks={results[0]['tracks']} · "
        f"context_reliability={results[0]['rel']} · NOT an 'unusual event' detector",
        fill=(235, 235, 235),
        font=font,
    )
    board.save(hero, optimize=True)
    print(f"hero -> {hero} {board.size}")

    # Touch mtimes so UI cache busts
    now = time.time()
    for i in range(1, len(results) + 1):
        p = FRAMES / f"latest_cam{i}.jpg"
        p.touch()
        # ensure mtime now
        import os

        os.utime(p, (now, now))
    print("seeded tmp/camera_frames/latest_cam{{1..N}}.jpg for console preview")


if __name__ == "__main__":
    main()
