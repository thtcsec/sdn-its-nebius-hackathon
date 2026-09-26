#!/usr/bin/env python
"""End-to-end demo flow check against a running console on :8080."""
from __future__ import annotations

import json
import sys
import time
from typing import Any

import requests

BASE = "http://127.0.0.1:8080"
TIMEOUT = 45


def get(path: str) -> Any:
    r = requests.get(BASE + path, timeout=TIMEOUT)
    r.raise_for_status()
    ct = r.headers.get("content-type", "")
    if "json" in ct:
        return r.json()
    return {"_status": r.status_code, "_bytes": len(r.content)}


def post(path: str, body: dict | None = None) -> Any:
    r = requests.post(BASE + path, json=body or {}, timeout=TIMEOUT)
    try:
        data = r.json()
    except Exception:
        data = {"_raw": r.text[:300]}
    if r.status_code >= 400:
        raise RuntimeError(f"POST {path} -> {r.status_code}: {data}")
    return data


def ok(name: str, cond: bool, detail: str = "") -> bool:
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return cond


def alert(attack_type: str, src_ip: str, dominance: float, cooldown: float, cam_scenario: str) -> dict:
    return post(
        "/api/v1/anomaly_alert",
        {
            "alert_id": f"E2E-{int(time.time()*1000)%100000}",
            "dpid": "0000000000000001",
            "src_ip": src_ip,
            "attack_type": attack_type,
            "prediction": attack_type,
            "reconstruction_error": 120.0,
            "confidence": 0.98,
            "cooldown_seconds": cooldown,
            "camera_scenario": cam_scenario,
            "source_dominance": dominance,
            "packet_in_delta_pct": 400 if dominance > 0.5 else 220,
            "distributed_sources": dominance < 0.45,
        },
    )


def main() -> int:
    fails = 0
    warns = 0
    print(f"=== E2E flow check @ {BASE} ===\n")

    try:
        html = requests.get(BASE + "/", timeout=TIMEOUT)
        fails += not ok("Dashboard HTML", html.status_code == 200 and "btn-lang" in html.text, f"status={html.status_code}")
    except Exception as e:
        ok("Dashboard HTML", False, str(e))
        return 1

    st = get("/api/v1/status")
    fails += not ok("Status API", isinstance(st, dict) and bool(st), f"keys={list(st.keys())[:10]}")
    print("    status:", json.dumps({k: st.get(k) for k in ("status", "model_loaded", "of_backend", "mode", "version") if k in st or True}, default=str)[:350])

    settings = get("/api/v1/settings")
    print("    settings keys:", list(settings.keys())[:12])

    updated = post("/api/v1/settings", {"lab_mode": False, "scenario_override": True})
    rt = updated.get("runtime") or updated.get("settings") or updated
    # settings payload nests console_defaults
    nested = (updated.get("settings") or {}).get("console_defaults") or {}
    lab = rt.get("lab_mode", nested.get("lab_mode"))
    ov = rt.get("scenario_override", nested.get("scenario_override"))
    # also check settings.runtime after GET
    settings2 = get("/api/v1/settings")
    cd = settings2.get("console_defaults") or {}
    lab = settings2.get("lab_mode", cd.get("lab_mode", lab))
    ov = settings2.get("scenario_override", cd.get("scenario_override", ov))
    # controller runtime may be top-level in settings
    if "runtime" in updated:
        lab = updated["runtime"].get("lab_mode", lab)
        ov = updated["runtime"].get("scenario_override", ov)
    fails += not ok("Settings → demo injects", lab is False and ov is True, f"lab_mode={lab} scenario_override={ov} runtime={updated.get('runtime')}")

    # Infer like the UI button
    for scen in ("normal", "ddos", "rush_hour"):
        try:
            inf = post("/api/v1/infer", {"scenario": scen, "adapt_tau": False})
            pred = inf.get("prediction") or inf.get("predicted_label") or inf.get("attack_type")
            fails += not ok(
                f"Infer scenario={scen}",
                "reconstruction_error" in inf or pred is not None,
                f"pred={pred} RE={inf.get('reconstruction_error')} mode={inf.get('mode')} source={inf.get('source')}",
            )
        except Exception as e:
            fails += not ok(f"Infer scenario={scen}", False, str(e))

    telem = get("/api/v1/telemetry")
    fails += not ok("Telemetry API", isinstance(telem, dict), f"keys={list(telem.keys())[:10]}")

    # Camera
    cam = get("/api/v1/camera")
    agg = cam.get("aggregate") or {}
    cams = cam.get("cameras") or []
    fails += not ok("Camera API loaded", len(cams) >= 1, f"n={len(cams)}")
    live = int(agg.get("live_rtsp") or 0)
    if live == 0 or not agg.get("frame_fresh"):
        warns += 1
        print(
            f"[WARN] Live RTSP unavailable (live_rtsp={live}, frame_fresh={agg.get('frame_fresh')}, "
            f"stream_available={agg.get('stream_available')}, source={agg.get('source')})"
        )
        for c in cams:
            err = (c.get("last_error") or "")[:100]
            print(f"    {c.get('camera_id')}: connected={c.get('connected')} err={err!r}")
    else:
        ok("Live RTSP", True, f"live_rtsp={live}")

    for c in cams:
        prev = c.get("preview_url")
        if not prev:
            fails += not ok(f"Preview URL {c.get('camera_id')}", False, "missing")
            continue
        pr = requests.get(BASE + prev, timeout=TIMEOUT)
        fails += not ok(
            f"Preview JPEG {c.get('camera_id')}",
            pr.status_code == 200 and len(pr.content) > 500,
            f"bytes={len(pr.content)} stale_ok_if_rtsp_down",
        )

    # Synthetic camera scenarios (demo-critical)
    for scen in ("rush", "attack_physical_stable", "mixed", "idle"):
        sc = post("/api/v1/camera/scenario", {"scenario": scen})
        fails += not ok(f"Set camera scenario={scen}", sc.get("scenario") == scen, f"got={sc.get('scenario')}")

    # Fusion preview: rush + low dominance
    post("/api/v1/camera/scenario", {"scenario": "rush"})
    fus = post(
        "/api/v1/camera/fusion_preview",
        {"network_prediction": "DDoS_PacketIn_Flood", "source_dominance": 0.30},
    )
    act = fus.get("recommended_action")
    fails += not ok(
        "Fusion preview rush+low-dom → preserve",
        act == "preserve_rush_hour" or (act and "preserve" in act),
        f"action={act} phys={fus.get('physical_context')} reasons={fus.get('reason_codes')}",
    )

    # Fusion preview: stable + high dominance
    post("/api/v1/camera/scenario", {"scenario": "attack_physical_stable"})
    fus2 = post(
        "/api/v1/camera/fusion_preview",
        {"network_prediction": "DDoS_PacketIn_Flood", "source_dominance": 0.82},
    )
    act2 = fus2.get("recommended_action")
    fails += not ok(
        "Fusion preview stable+high-dom → contain",
        act2 in {"temporary_drop", "rate_limit"} or (act2 and ("drop" in act2 or "rate" in act2)),
        f"action={act2} phys={fus2.get('physical_context')}",
    )

    # UI-equivalent alert path
    post("/api/v1/camera/scenario", {"scenario": "rush"})
    e2e = alert("DDoS_PacketIn_Flood", "10.0.0.12", 0.32, 0.0, "rush")
    fus_e = e2e.get("fusion") or {}
    fails += not ok(
        "Alert+fusion rush/low-dom",
        fus_e.get("recommended_action") in {"preserve_rush_hour", "temporary_drop", "rate_limit", "observe"}
        and fus_e.get("recommended_action") is not None,
        f"action={fus_e.get('recommended_action')} phys={fus_e.get('physical_context')} fp={fus_e.get('false_positive_corrected')}",
    )
    # Prefer preserve here
    if fus_e.get("recommended_action") != "preserve_rush_hour":
        warns += 1
        print(f"[WARN] Expected preserve_rush_hour for rush+0.32, got {fus_e.get('recommended_action')}")

    post("/api/v1/camera/scenario", {"scenario": "attack_physical_stable"})
    e2e2 = alert("DDoS_PacketIn_Flood", "10.0.0.15", 0.85, 12.0, "attack_physical_stable")
    fus_e2 = e2e2.get("fusion") or {}
    fails += not ok(
        "Alert+fusion stable/high-dom contain",
        fus_e2.get("recommended_action") not in {None, "preserve_rush_hour"},
        f"action={fus_e2.get('recommended_action')}",
    )

    rules = get("/api/v1/active_rules")
    fails += not ok(
        "Active rules (mock OK)",
        isinstance(rules, dict) and "active_rules" in rules,
        f"count={rules.get('count')} evidence={rules.get('network_evidence')} note={rules.get('actuation_note')}",
    )

    fails += not ok("Lab API", isinstance(get("/api/v1/lab"), dict))
    fails += not ok("Topology API", isinstance(get("/api/v1/topology"), dict))
    fails += not ok("Empirical API", isinstance(get("/api/v1/empirical"), dict))

    try:
        rp = post("/api/v1/replay", {"script": "ddos_cycle", "action": "start"})
        fails += not ok("Replay start", isinstance(rp, dict), str(list(rp.keys())[:8]))
        time.sleep(0.8)
        post("/api/v1/replay", {"action": "stop"})
    except Exception as e:
        # some APIs use different shape
        try:
            rp = post("/api/v1/replay", {"script": "ddos_cycle"})
            fails += not ok("Replay POST", isinstance(rp, dict), str(rp)[:160])
        except Exception as e2:
            fails += not ok("Replay", False, f"{e} | {e2}")

    print("\n=== SUMMARY ===")
    print(f"FAIL={fails} WARN={warns}")
    if fails:
        print("Critical demo path has failures.")
        return 1
    if warns:
        print("Critical demo path OK; live RTSP / minor fusion WARN — demo with Cam·synth.")
    else:
        print("Everything critical PASS including live RTSP.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
