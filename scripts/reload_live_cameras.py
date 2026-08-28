#!/usr/bin/env python
"""Reload cameras.local.yaml selection and wait for live RTSP evidence."""
from __future__ import annotations

import json
import time

import requests

B = "http://127.0.0.1:8080"


def main() -> None:
    r = requests.post(B + "/api/v1/camera/reload", timeout=180)
    print("reload", r.status_code)
    snap = r.json().get("snapshot") or r.json()
    cfg = snap.get("config") or {}
    print("select_mode", cfg.get("select_mode"), "local", cfg.get("local_override"))
    print("selected", json.dumps(cfg.get("selected_ids"), ensure_ascii=False))

    for i in range(10):
        time.sleep(5)
        cam = requests.get(B + "/api/v1/camera", timeout=90).json()
        agg = cam.get("aggregate") or {}
        det = agg.get("detector") or {}
        print(
            f"t+{(i+1)*5}s live={agg.get('live_rtsp')} fresh={agg.get('frame_fresh')} "
            f"stream={agg.get('stream_available')} source={agg.get('source')} "
            f"tracks={agg.get('visible_vehicle_tracks')} phys={agg.get('physical_label')} "
            f"det_loaded={det.get('loaded')} last_ms={det.get('last_infer_ms')}"
        )
        for c in cam.get("cameras") or []:
            q = c.get("quality") or {}
            err = (c.get("last_error") or "")[:90]
            print(
                f"  {c.get('camera_id')} conn={c.get('connected')} "
                f"fresh={q.get('frame_fresh')} stream={q.get('stream_available')} err={err!r}"
            )
        if int(agg.get("live_rtsp") or 0) > 0:
            # even if not all fresh, live>0 is enough to proceed
            if agg.get("frame_fresh") or i >= 3:
                break

    # vars dump
    st = requests.get(B + "/api/v1/status", timeout=30).json()
    settings = requests.get(B + "/api/v1/settings", timeout=30).json()
    rt = settings.get("runtime") or {}
    print("\n=== RUNTIME VARS ===")
    for k in (
        "status",
        "model_loaded",
        "of_backend",
        "network_evidence",
        "lab_mode",
        "scenario_override",
        "load_error",
    ):
        print(f"  status.{k}={st.get(k)}")
    for k in (
        "lab_mode",
        "scenario_override",
        "tau",
        "poll_ms",
        "ddos_cooldown",
        "theme",
        "dataset_mode",
    ):
        print(f"  runtime.{k}={rt.get(k)}")


if __name__ == "__main__":
    main()
