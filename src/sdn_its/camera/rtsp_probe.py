"""Bounded RTSP health probe + optional single-frame sample (no archive)."""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any


def probe_stream(url: str, *, timeout_s: float = 12.0) -> dict[str, Any]:
    """ffprobe video stream metadata. Never logs the raw URL."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-rtsp_transport",
        "tcp",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,width,height,avg_frame_rate",
        "-of",
        "json",
        url,
    ]
    t0 = time.perf_counter()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s + 2)
        ms = round((time.perf_counter() - t0) * 1000.0, 1)
        if p.returncode != 0:
            return {"ok": False, "latency_ms": ms, "error": _scrub(p.stderr or "ffprobe_failed")[:200]}
        data = json.loads(p.stdout or "{}")
        st = (data.get("streams") or [{}])[0]
        fps = _fps(st.get("avg_frame_rate"))
        return {
            "ok": True,
            "latency_ms": ms,
            "codec": st.get("codec_name"),
            "width": st.get("width"),
            "height": st.get("height"),
            "fps": fps,
            "resolution": (
                f"{st.get('width')}x{st.get('height')}" if st.get("width") and st.get("height") else None
            ),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "latency_ms": round((time.perf_counter() - t0) * 1000.0, 1), "error": str(exc)[:200]}


def grab_latest_frame(
    url: str,
    dest: Path,
    *,
    timeout_s: float = 20.0,
    max_bytes: int = 2_500_000,
) -> dict[str, Any]:
    """Overwrite a single JPEG for this camera. Deletes if oversized."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-rtsp_transport",
        "tcp",
        "-i",
        url,
        "-frames:v",
        "1",
        "-update",
        "1",
        "-q:v",
        "3",
        str(dest),
    ]
    t0 = time.perf_counter()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        ms = round((time.perf_counter() - t0) * 1000.0, 1)
        if p.returncode != 0 or not dest.is_file():
            return {"ok": False, "latency_ms": ms, "error": _scrub(p.stderr or "ffmpeg_failed")[:200]}
        size = dest.stat().st_size
        if size > max_bytes:
            dest.unlink(missing_ok=True)
            return {"ok": False, "latency_ms": ms, "error": f"frame_too_large:{size}"}
        activity = estimate_activity(dest)
        return {"ok": True, "latency_ms": ms, "path": str(dest), "bytes": size, **activity}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "latency_ms": round((time.perf_counter() - t0) * 1000.0, 1), "error": str(exc)[:200]}


def estimate_activity(image_path: Path) -> dict[str, Any]:
    """Cheap edge-energy proxy — NOT a vehicle detector. Labeled as rtsp_proxy."""
    try:
        from PIL import Image
        import numpy as np

        im = Image.open(image_path).convert("L").resize((320, 180))
        arr = np.asarray(im, dtype=np.float32)
        # Sobel-ish energy
        gx = np.abs(arr[:, 1:] - arr[:, :-1]).mean()
        gy = np.abs(arr[1:, :] - arr[:-1, :]).mean()
        energy = float(gx + gy)
        # Map energy bands → rough counts for fusion demos (honest source tag)
        if energy > 28:
            vehicles, queue, label = 32, 45.0, "rush_hour"
        elif energy > 18:
            vehicles, queue, label = 16, 22.0, "elevated"
        elif energy > 10:
            vehicles, queue, label = 7, 8.0, "stable"
        else:
            vehicles, queue, label = 2, 3.0, "stable"
        return {
            "edge_energy": round(energy, 2),
            "vehicle_count_proxy": vehicles,
            "queue_length_m_proxy": queue,
            "physical_label_proxy": label,
        }
    except Exception:
        return {"edge_energy": None, "vehicle_count_proxy": None}


def _fps(s: str | None) -> float | None:
    if not s or s == "0/0":
        return None
    if "/" in s:
        a, b = s.split("/", 1)
        try:
            return round(float(a) / float(b), 2) if float(b) else None
        except ValueError:
            return None
    try:
        return float(s)
    except ValueError:
        return None


def _scrub(text: str) -> str:
    return re.sub(r"//[^/\s]+:[^/\s]+@", "//***:***@", text or "")
