#!/usr/bin/env python3
"""Sensitivity sweep over fusion dominance thresholds (handcrafted rules).

Does NOT claim empirical FP reduction from real cameras — only shows how
preserve vs contain flips when dominance cutoff changes for fixed synthetic cases.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sdn_its.camera.fusion import FusionEngine


def _case(phys: dict, net: str, dominance: float, pin: float = 400.0):
    d = FusionEngine().fuse(
        network_prediction=net,
        physical=phys,
        source_dominance=dominance,
        distributed_sources=dominance < 0.45,
        packet_in_delta_pct=pin,
    )
    return d.recommended_action, d.false_positive_corrected


def main() -> int:
    rush = {
        "physical_label": "rush_hour",
        "is_vehicle_count": True,
        "vehicle_count": 40,
        "queue_length_m": 50,
        "activity_band": "high",
        "stale": False,
        "analytics_valid": True,
    }
    stable = {
        "physical_label": "stable",
        "is_vehicle_count": True,
        "vehicle_count": 5,
        "queue_length_m": 4,
        "activity_band": "low",
        "stale": False,
        "analytics_valid": True,
    }
    thresholds = [0.55, 0.65, 0.75, 0.85]
    rows = []
    for thr in thresholds:
        # Case A: rush + mid dominance → preserve when distributed (dom < 0.45)
        # Sweep: at each thr, ask "would single-source mixed contain?" using dom=thr
        a_act, a_fp = _case(rush, "DDoS_PacketIn_Flood", dominance=0.30)
        # False preserve: treat as rush when dominance is high (should isolate)
        mixed_act, _ = _case(rush, "DDoS_PacketIn_Flood", dominance=thr)
        # False contain: stable camera should contain when dominance >= ~0.55
        b_act, _ = _case(stable, "DDoS_PacketIn_Flood", dominance=thr)
        false_preserve = mixed_act == "preserve_rush_hour" and thr >= 0.7
        false_contain = b_act in {"preserve_rush_hour", "observe"} and thr >= 0.55
        rows.append(
            {
                "dominance_threshold_probe": thr,
                "A_rush_distributed_action": a_act,
                "A_fp_corrected": a_fp,
                "mixed_at_dom=thr_action": mixed_act,
                "B_stable_at_dom=thr_action": b_act,
                "false_preserve_risk": false_preserve,
                "false_contain_risk": false_contain,
                "note": (
                    "false_preserve_risk: rush+high-dom still preserve (missed isolate); "
                    "false_contain_risk: stable+dom fails to contain"
                ),
            }
        )

    payload = {
        "experiment": "B_C_sensitivity",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "honesty": (
            "Handcrafted thresholds; this table is a sensitivity check, not a validated ROC. "
            "Production would need labeled multimodal traces."
        ),
        "rows": rows,
    }
    out = ROOT / "artifacts" / "results" / "exp_bc" / "exp_bc_sensitivity.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    print(json.dumps({"rows": rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
