#!/usr/bin/env python3
"""Experiments B/C — camera-assisted fusion (synthetic physical context).

Scenario A (legitimate surge):
  camera=rush, network=DDoS-like features but distributed → PRESERVE

Scenario B (PacketIn flood):
  camera=stable, network=DDoS, single-source → TEMPORARY DROP

Scenario C (mixed):
  camera=rush + ped, network=DDoS, single-source → isolate source (DROP src)
  without treating whole junction as blockable rush-only

Writes artifacts/results/exp_bc/exp_bc_fusion.json
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import threading

from sdn_its.camera.fusion import FusionEngine
from sdn_its.camera.store import CameraContextStore
from sdn_its.mitigation.containment import ContainmentEngine
from sdn_its.mitigation.policy_engine import PolicyEngine


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_case(name: str, *, scenario: str, net: str, dominance: float, pin: float) -> dict:
    store = CameraContextStore()
    store.set_scenario(scenario)
    store._emit_synthetic()  # noqa: SLF001 — force one publish tick
    physical = store.aggregate_context()
    fusion = FusionEngine().fuse(
        network_prediction=net,
        physical=physical,
        source_dominance=dominance,
        distributed_sources=dominance < 0.45,
        packet_in_delta_pct=pin,
    )
    eng = PolicyEngine(ContainmentEngine({}, threading.RLock(), None))
    result = eng.apply(
        attack_type=net,
        dpid="0000000000000001",
        src_ip="10.0.0.15",
        cooldown=15.0,
        fusion=fusion.to_dict(),
    )
    return {
        "scenario": name,
        "camera_scenario": scenario,
        "network_prediction": net,
        "source_dominance": dominance,
        "physical": physical,
        "fusion": fusion.to_dict(),
        "mitigation_status": result.mitigation_status,
        "rules": len(result.applied_rules),
        "false_positive_corrected": result.false_positive_avoided,
    }


def main() -> int:
    cases = [
        run_case(
            "A_legitimate_surge",
            scenario="rush",
            net="DDoS_PacketIn_Flood",
            dominance=0.30,
            pin=418.0,
        ),
        run_case(
            "B_packetin_flood",
            scenario="attack_physical_stable",
            net="DDoS_PacketIn_Flood",
            dominance=0.82,
            pin=418.0,
        ),
        run_case(
            "C_mixed_rush_and_attack",
            scenario="mixed",
            net="DDoS_PacketIn_Flood",
            dominance=0.82,
            pin=350.0,
        ),
    ]
    # Pass criteria (research narrative)
    a, b, c = cases
    summary = {
        "A_preserves": a["mitigation_status"]
        in {"IGNORED_BENIGN_RUSH_HOUR", "PROTECTED_SAFETY_CRITICAL", "OBSERVE_ONLY"},
        "A_fp_corrected": a["false_positive_corrected"] is True,
        "B_contains": b["rules"] > 0,
        "C_isolates_source": c["rules"] > 0
        and c["fusion"]["recommended_action"] == "temporary_drop",
        "C_physical_rush": c["physical"]["physical_label"] in {"rush_hour", "mixed_busy", "elevated"},
    }
    payload = {
        "experiment": "B_C",
        "title": "Camera-assisted safety-aware fusion",
        "generated_at": _utc(),
        "note": (
            "Synthetic edge analytics (vehicle_count / queue / ped / incident) with "
            "is_vehicle_count=true for rule tests. pass=true proves fusion rules match "
            "scripted inputs — NOT that live RTSP/edge-energy reduces false positives. "
            "Live RTSP uses visual_activity_proxy only until a real detector exists."
        ),
        "honesty": {
            "claim": "explainable multimodal fusion rules",
            "not_claimed": [
                "YOLO / tracker accuracy",
                "real-camera false-positive reduction",
                "OpenFlow outcome (see Exp A for network evidence)",
            ],
        },
        "cases": cases,
        "summary": summary,
        "pass": all(summary.values()),
    }
    out_dirs = [
        ROOT / "artifacts" / "results" / "exp_bc",
        ROOT / "experiments" / "exp05_drl" / "results",
    ]
    for d in out_dirs:
        d.mkdir(parents=True, exist_ok=True)
        path = d / "exp_bc_fusion.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote {path}")
    print(json.dumps({"pass": payload["pass"], "summary": summary}, indent=2))
    return 0 if payload["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
