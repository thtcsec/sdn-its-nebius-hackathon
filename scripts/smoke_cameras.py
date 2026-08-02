#!/usr/bin/env python3
"""Smoke: load allow-list from configs/cameras.yaml and print live probe status."""

from __future__ import annotations

import time

from sdn_its.camera.store import get_camera_store


def main() -> int:
    store = get_camera_store(reload=True)
    print("config:", store.snapshot().get("config"))
    for i in range(8):
        time.sleep(8)
        snap = store.snapshot()
        agg = snap["aggregate"]
        va = agg.get("visual_activity") or {}
        print(
            f"t+{(i+1)*8}s live={agg.get('live_rtsp')} band={agg.get('activity_band')} "
            f"energy={va.get('value')} is_vc={agg.get('is_vehicle_count')} "
            f"label={agg.get('physical_label')} analytics={agg.get('analytics_valid')} stale={agg.get('stale')}"
        )
        for c in snap["cameras"]:
            ctx = c.get("context") or {}
            q = c.get("quality") or {}
            print(
                f"  {c['camera_id']} conn={c['connected']} src={ctx.get('source')} "
                f"band={ctx.get('activity_band')} stream/frame/scene/an="
                f"{q.get('stream_available')}/{q.get('frame_fresh')}/{q.get('scene_valid')}/{q.get('analytics_valid')} "
                f"preview={bool(c.get('preview_url'))}"
            )
        live_ctx = any(
            str((c.get("context") or {}).get("source") or "").startswith("rtsp") for c in snap["cameras"]
        )
        if agg.get("live_rtsp", 0) >= 1 and live_ctx:
            print("OK — allow-list cameras producing RTSP-backed context")
            return 0
    print("TIMEOUT — check inventory URLs / network")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
