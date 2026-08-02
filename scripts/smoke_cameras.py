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
        print(
            f"t+{(i+1)*8}s live={agg.get('live_rtsp')} veh={agg.get('vehicle_count')} "
            f"label={agg.get('physical_label')} stale={agg.get('stale')}"
        )
        for c in snap["cameras"]:
            ctx = c.get("context") or {}
            print(
                f"  {c['camera_id']} conn={c['connected']} src={ctx.get('source')} "
                f"veh={ctx.get('vehicle_count')} codec={c.get('codec')} frame={bool(c.get('latest_frame'))}"
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
