#!/usr/bin/env python3
"""Sensitivity sweep — inject FusionThresholds and show preserve/contain trade-offs.

Sweeps dominance_mixed_isolate and dominance_stable_contain on fixed boundary cases.
Does NOT claim empirical camera FP reduction.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sdn_its.camera.fusion import FusionEngine, FusionThresholds


def _act(th: FusionThresholds, phys: dict, net: str, dominance: float, pin: float = 400.0) -> str:
    d = FusionEngine(th).fuse(
        network_prediction=net,
        physical=phys,
        source_dominance=dominance,
        distributed_sources=dominance < th.distributed_below,
        packet_in_delta_pct=pin,
    )
    return d.recommended_action


def main() -> int:
    rush = {
        "physical_label": "rush_hour",
        "is_vehicle_count": True,
        "visible_vehicle_tracks": 40,
        "vehicle_count": 40,
        "queue_length_proxy_m": 50,
        "activity_band": "high",
        "stale": False,
        "analytics_valid": True,
        "pedestrian_present": False,
    }
    stable = {
        "physical_label": "stable",
        "is_vehicle_count": True,
        "visible_vehicle_tracks": 5,
        "vehicle_count": 5,
        "queue_length_proxy_m": 4,
        "activity_band": "low",
        "stale": False,
        "analytics_valid": True,
        "pedestrian_present": False,
    }
    # Boundary dominance: just below / at / above mixed-isolate default
    probe_dom = 0.62  # between distributed_below(0.45) and typical isolate(0.7)

    thresholds = [0.55, 0.65, 0.75, 0.85]
    rows = []
    for thr in thresholds:
        th_mixed = FusionThresholds(dominance_mixed_isolate=thr, dominance_stable_contain=0.55)
        th_stable = FusionThresholds(dominance_mixed_isolate=0.70, dominance_stable_contain=thr)

        # At fixed dominance=probe_dom: lowering isolate threshold → more contain on rush+attack
        rush_at_probe = _act(th_mixed, rush, "DDoS_PacketIn_Flood", dominance=probe_dom)
        # Distributed rush should still preserve (dom=0.30 < distributed_below)
        rush_distributed = _act(th_mixed, rush, "DDoS_PacketIn_Flood", dominance=0.30)
        # Stable + anomaly: raising stable_contain threshold → fewer contains at mid dominance
        stable_at_mid = _act(th_stable, stable, "DDoS_PacketIn_Flood", dominance=0.60)

        false_preserve = rush_at_probe == "preserve_rush_hour"  # missed isolate when thr low enough to expect drop
        # When thr <= probe_dom, isolate branch should fire → temporary_drop expected
        expect_isolate = thr <= probe_dom
        false_preserve_risk = expect_isolate and rush_at_probe != "temporary_drop"
        # When thr > 0.60, stable mid-dom should soft rate-limit — hard DROP is false-contain
        expect_stable_contain = thr <= 0.60
        false_contain_risk = (not expect_stable_contain) and stable_at_mid == "temporary_drop"
        missed_contain_risk = expect_stable_contain and stable_at_mid != "temporary_drop"

        rows.append(
            {
                "threshold": thr,
                "probe_dominance": probe_dom,
                "rush_dom=probe_action": rush_at_probe,
                "rush_dom=0.30_action": rush_distributed,
                "stable_dom=0.60_action": stable_at_mid,
                "expect_isolate_at_probe": expect_isolate,
                "false_preserve_risk": false_preserve_risk,
                "expect_stable_contain_at_0.60": expect_stable_contain,
                "false_contain_risk": false_contain_risk,
                "missed_contain_risk": missed_contain_risk,
                "tradeoff_note": (
                    "Lower dominance_mixed_isolate → more temporary_drop on rush+mid-dom "
                    "(fewer false-preserve, more aggressive isolate). "
                    "Higher dominance_stable_contain → fewer contains on stable+mid-dom."
                ),
            }
        )

    # Compact trade-off counts
    tradeoff = {
        "false_preserve_count": sum(1 for r in rows if r["false_preserve_risk"]),
        "false_contain_count": sum(1 for r in rows if r["false_contain_risk"]),
        "missed_contain_count": sum(1 for r in rows if r["missed_contain_risk"]),
        "actions_at_probe_vary": len({r["rush_dom=probe_action"] for r in rows}) > 1,
        "actions_stable_vary": len({r["stable_dom=0.60_action"] for r in rows}) > 1,
    }

    payload = {
        "experiment": "B_C_sensitivity",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "honesty": (
                "Thresholds are injected into FusionEngine (FusionThresholds). "
                "Trade-off appears when mid-dominance cases flip: "
                "low isolate thr → temporary_drop on rush+mid-dom; "
                "high isolate thr → preserve_rush_hour; "
                "low stable-contain thr → temporary_drop on stable+mid-dom; "
                "high stable-contain thr → rate_limit. "
                "Not a ROC on labeled video."
            ),
        "method": {
            "swept": ["dominance_mixed_isolate", "dominance_stable_contain"],
            "fixed_probe_dominance": probe_dom,
            "cases": ["rush+DDoS", "stable+DDoS"],
        },
        "rows": rows,
        "tradeoff": tradeoff,
    }
    out = ROOT / "artifacts" / "results" / "exp_bc" / "exp_bc_sensitivity.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    print(json.dumps({"tradeoff": tradeoff, "rows": rows}, indent=2))
    return 0 if tradeoff["actions_at_probe_vary"] or tradeoff["actions_stable_vary"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
