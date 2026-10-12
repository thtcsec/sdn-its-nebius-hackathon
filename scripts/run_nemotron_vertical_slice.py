#!/usr/bin/env python3
"""Minimal vertical slice: telemetry + camera → Nemotron → schema → safety → PolicyEngine.

Loads credentials from repository-root ``.env`` (process env wins).
Demo mode defaults: containment intentions blocked; OpenFlow not pushed here.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from sdn_its.utils.env import ensure_repo_env, nebius_config_summary  # noqa: E402
from sdn_its.llm.investigation import IncidentContext, investigate_incident  # noqa: E402
from sdn_its.llm.nebius_client import resolve_model  # noqa: E402
from sdn_its.controller.flow_manager import FlowRuleManager  # noqa: E402
from sdn_its.mitigation.policy_engine import PolicyEngine  # noqa: E402


def _sample_context() -> IncidentContext:
    """Synthetic incident context for the slice (labeled synthetic in artifact)."""
    rule_fusion = {
        "recommended_action": "rate_limit",
        "policy_attack_type": "LOFT_LowRate_Attack",
        "cooldown_seconds": 15.0,
        "false_positive_corrected": False,
        "safety_critical": False,
        "physical_label": "stable",
        "explain": "rule baseline: anomaly + stable camera → rate_limit",
    }
    return IncidentContext(
        network_prediction="LOFT_LowRate_Attack",
        telemetry={
            "context_source": "synthetic_fixture",
            "packet_in_delta_pct": 42.0,
            "source_dominance": 0.61,
            "distributed_sources": False,
            "window_id": "slice-demo-001",
        },
        camera={
            "context_source": "synthetic_fixture",
            "physical_label": "stable",
            "visible_vehicle_tracks": 3,
            "queue_length_proxy_m": 8.0,
            "stream_available": False,
            "analytics_valid": False,
        },
        rule_fusion=rule_fusion,
        dpid="1",
        src_ip="10.0.0.15",
    )


def main() -> int:
    ensure_repo_env()
    parser = argparse.ArgumentParser(description="Nemotron vertical slice (Nebius)")
    parser.add_argument("--model", default=None)
    parser.add_argument("--demo-mode", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--allow-containment-in-demo", action="store_true", default=False)
    parser.add_argument(
        "--out",
        default=str(ROOT / "artifacts" / "hackathon" / "vertical_slice_last.json"),
    )
    args = parser.parse_args()

    model = resolve_model(args.model)
    ctx = _sample_context()
    result = investigate_incident(
        ctx,
        demo_mode=args.demo_mode,
        allow_containment_in_demo=args.allow_containment_in_demo,
        model=model,
    )

    policy_status = None
    applied_rules: list = []
    if result.ok and result.fusion_for_policy is not None:
        engine = PolicyEngine(FlowRuleManager(of_push_callback=None).containment)
        mit = engine.apply(
            attack_type=ctx.network_prediction,
            dpid=ctx.dpid,
            src_ip=ctx.src_ip,
            fusion=result.fusion_for_policy,
        )
        policy_status = mit.mitigation_status
        applied_rules = mit.applied_rules

    artifact = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "slice": "telemetry_camera_nemotron_policy_v1",
        "context_source": "synthetic_fixture",
        "demo_mode": args.demo_mode,
        "requested_model": model,
        "config": nebius_config_summary(),
        "of_backend_note": "PolicyEngine only creates in-memory FlowRule objects here; "
        "default controller of_backend remains mock (no switch push in this script).",
        "investigation": result.to_dict(),
        "policy_mitigation_status": policy_status,
        "policy_applied_rules_count": len(applied_rules),
        "validated_decision": result.recommendation.to_dict() if result.recommendation else None,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf-8")
    print(json.dumps(artifact, indent=2, default=str))
    print(f"wrote {out_path}")

    if result.evidence_class == "blocked_no_credentials":
        return 2
    if not result.ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
