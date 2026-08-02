#!/usr/bin/env python3
"""Experiment D — camera tracker × fusion phases (honest evidence grades).

Arms
----
live_arm      : unmodified detector aggregate (may NOT be congested).
scripted_arm  : explicit congestion context for rule wiring only.

Summary always separates:
  detector_live
  physical_context_modified
  evidence_grade   (live_observation | scripted)
  openflow_evidence (false unless --with-of verifies dump-flows)

pass / pass_scripted_rules only claims scripted fusion wiring — never “live congestion observed”.

  python scripts/exp_d_camera_containment.py
  python scripts/exp_d_camera_containment.py --with-of
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sdn_its.camera.fusion import FusionEngine
from sdn_its.camera.store import get_camera_store
from sdn_its.mitigation.containment import ContainmentEngine
from sdn_its.mitigation.policy_engine import PolicyEngine


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _wait_detector(store, timeout_s: float = 45.0) -> dict:
    store.set_scenario("idle")
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        cards = store.list_cards()
        live = [
            c
            for c in cards
            if (c.get("context") or {}).get("is_vehicle_count")
            and str((c.get("context") or {}).get("source") or "").startswith("detector")
        ]
        if live:
            return store.aggregate_context()
        time.sleep(2.0)
    return store.aggregate_context()


def _phys_snip(physical: dict) -> dict:
    keys = (
        "visible_vehicle_tracks",
        "vehicle_count",
        "occupancy_ratio",
        "queue_length_proxy_m",
        "pedestrian_count",
        "physical_label",
        "is_vehicle_count",
        "source",
        "context_reliability",
    )
    return {k: physical.get(k) for k in keys}


def _phase(name: str, *, net: str, dominance: float, pin: float, physical: dict) -> dict:
    physical = dict(physical)
    physical.setdefault("stale", False)
    physical.setdefault("analytics_valid", True)
    if physical.get("visible_vehicle_tracks") is None and physical.get("vehicle_count") is not None:
        physical["visible_vehicle_tracks"] = physical["vehicle_count"]
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
        cooldown=12.0,
        fusion=fusion.to_dict(),
    )
    return {
        "phase": name,
        "network_prediction": net,
        "source_dominance": dominance,
        "physical": _phys_snip(physical),
        "fusion": fusion.to_dict(),
        "mitigation_status": result.mitigation_status,
        "rules": len(result.applied_rules),
        "false_positive_corrected": result.false_positive_avoided,
    }


def _arm_phases(physical: dict) -> list[dict]:
    return [
        _phase("1_congestion_preserve", net="DDoS_PacketIn_Flood", dominance=0.30, pin=250.0, physical=physical),
        _phase("2_attack_into_congestion", net="DDoS_PacketIn_Flood", dominance=0.82, pin=400.0, physical=physical),
    ]


def _preserves(p: dict) -> bool:
    return p["mitigation_status"] in {
        "IGNORED_BENIGN_RUSH_HOUR",
        "PROTECTED_SAFETY_CRITICAL",
        "OBSERVE_ONLY",
    }


def _contains(p: dict) -> bool:
    return p["rules"] > 0 and p["fusion"]["recommended_action"] == "temporary_drop"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-of", action="store_true", help="Attempt ovs-ofctl verify (Linux/WSL)")
    ap.add_argument("--timeout", type=float, default=45.0)
    args = ap.parse_args()

    store = get_camera_store(reload=True)
    live_physical = dict(_wait_detector(store, timeout_s=args.timeout))
    detector_live = bool(
        live_physical.get("is_vehicle_count")
        and (
            live_physical.get("visible_vehicle_tracks") is not None
            or live_physical.get("vehicle_count") is not None
        )
        and str(live_physical.get("source") or "").startswith("detector")
    )
    # Congestion = rush label or strong proxies — not merely tracks ≥ tracks_rush_min (12).
    live_congested = (
        live_physical.get("physical_label") in {"rush_hour", "elevated", "mixed_busy"}
        or int(live_physical.get("visible_vehicle_tracks") or live_physical.get("vehicle_count") or 0) >= 25
        or float(live_physical.get("occupancy_ratio") or 0) >= 0.55
        or float(live_physical.get("queue_length_proxy_m") or live_physical.get("queue_length_m") or 0) >= 40.0
    )

    live_arm = {
        "evidence_grade": "live_observation",
        "detector_live": detector_live,
        "physical_context_modified": False,
        "live_was_congested": live_congested,
        "physical": _phys_snip(live_physical),
        "phases": _arm_phases(live_physical) if detector_live else [],
        "note": (
            "Unmodified detector aggregate. P1 preserve is NOT expected unless the scene "
            "is actually congested. This arm measures observation, not scripted pass."
        ),
    }
    if live_arm["phases"]:
        live_arm["P1_preserves"] = _preserves(live_arm["phases"][0])
        live_arm["P2_contains"] = _contains(live_arm["phases"][1])

    # Scripted congestion context — explicitly modified / synthetic
    scripted_physical = {
        "physical_label": "rush_hour",
        "is_vehicle_count": True,
        "visible_vehicle_tracks": 28,
        "vehicle_count": 28,
        "vehicle_flow_count": None,
        "queue_length_m": 42.0,
        "queue_length_proxy_m": 42.0,
        "occupancy_ratio": 0.55,
        "activity_band": "high",
        "pedestrian_present": False,
        "pedestrian_count": 0,
        "incident": False,
        "stale": False,
        "analytics_valid": True,
        "source": "scripted_congestion_context",
        "context_reliability": 0.5,
        "reliability_components": {"synthetic": True},
    }
    scripted_arm = {
        "evidence_grade": "scripted",
        "detector_live": detector_live,
        "physical_context_modified": True,
        "physical": _phys_snip(scripted_physical),
        "phases": _arm_phases(scripted_physical),
        "note": (
            "Explicit congestion inputs for fusion/policy wiring only. "
            "pass_scripted_rules does NOT mean live congestion was observed."
        ),
    }
    scripted_arm["P1_preserves"] = _preserves(scripted_arm["phases"][0])
    scripted_arm["P2_contains"] = _contains(scripted_arm["phases"][1])

    p3 = {
        "phase": "3_rollback",
        "evidence_grade": "not_run" if not args.with_of else "attempted",
        "openflow_evidence": False,
        "of_attempted": bool(args.with_of),
        "missing_metrics": [
            "ovs-ofctl dump-flows verify",
            "attack_throughput",
            "legitimate_throughput",
            "rtsp_packet_loss",
            "frame_latency_before_after",
            "rollback_verification",
        ],
        "expected_if_lab": "temporary rules expire; attack host recovers; legit + RTSP remain up",
        "note": "Closed-loop network outcome is Exp A / WSL Mininet — not proven by fusion objects alone.",
    }
    if args.with_of:
        try:
            sys.path.insert(0, str(ROOT / "scripts"))
            from exp_a_ddos_containment import dump_flows, ofctl_add_drop  # type: ignore

            add = ofctl_add_drop("10.0.0.15", hard=8, priority=200)
            time.sleep(1.0)
            dump1 = dump_flows()
            time.sleep(9.0)
            dump2 = dump_flows()
            p3["of"] = {"add": add, "dump_during": dump1[:800], "dump_after": dump2[:800]}
            p3["openflow_evidence"] = bool(add.get("ok") or add.get("verified"))
            p3["evidence_grade"] = "openflow_lab" if p3["openflow_evidence"] else "of_attempt_failed"
        except Exception as exc:  # noqa: BLE001
            p3["of_error"] = str(exc)[:300]
            p3["evidence_grade"] = "of_attempt_failed"

    summary = {
        "detector_live": detector_live,
        "physical_context_modified": True,  # scripted arm always modifies/creates congestion context
        "live_arm_modified": False,
        "evidence_grade": "scripted",  # claim grade for pass_* flags below
        "openflow_evidence": bool(p3.get("openflow_evidence")),
        "live_was_congested": live_congested,
        "live_snapshot": _phys_snip(live_physical),
        "pass_scripted_rules": bool(scripted_arm["P1_preserves"] and scripted_arm["P2_contains"]),
        "pass_live_observation_congestion": bool(detector_live and live_congested),
        "pass_live_P1_preserve": bool(live_arm.get("P1_preserves")),
        "pass_closed_loop_network": bool(p3.get("openflow_evidence")),
    }
    payload = {
        "experiment": "D",
        "title": "Camera tracker × fusion phases (graded evidence)",
        "generated_at": _utc(),
        "honesty": [
            "detector_live ≠ congestion observed ≠ OpenFlow outcome.",
            "pass_scripted_rules only proves fusion wiring on scripted congestion inputs.",
            "visible_vehicle_tracks are in-view tracks, not veh/h.",
            "context_reliability is a heuristic composite, not calibrated accuracy.",
            "Without --with-of, closed loop stops at in-memory mitigation objects.",
        ],
        "arms": {"live": live_arm, "scripted": scripted_arm},
        "phase3_rollback": p3,
        "summary": summary,
        # Back-compat key: scripted wiring only
        "pass": summary["pass_scripted_rules"],
    }
    out_dirs = [
        ROOT / "artifacts" / "results" / "exp_d",
        ROOT / "experiments" / "exp02_ddos" / "results",
    ]
    for d in out_dirs:
        d.mkdir(parents=True, exist_ok=True)
        path = d / "exp_d_phases.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote {path}")
    print(json.dumps({"pass": payload["pass"], "summary": summary}, indent=2))
    return 0 if summary["pass_scripted_rules"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
