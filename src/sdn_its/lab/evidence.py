"""Aggregate Traffic / Detection / Actuation / Outcome evidence for the console."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
EXP_A_CANDIDATES = [
    ROOT / "artifacts" / "results" / "exp_a" / "exp_a_metrics.json",
    ROOT / "experiments" / "exp02_ddos" / "results" / "exp_a_metrics.json",
]


def load_exp_a() -> dict[str, Any] | None:
    for p in EXP_A_CANDIDATES:
        if p.is_file():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
    return None


def build_evidence_board(controller) -> dict[str, Any]:
    """Four-column evidence board. Actuation/Outcome grey when no network evidence."""
    of: dict[str, Any] = {}
    try:
        of = controller.openflow_status(refresh=True)
    except Exception as exc:
        of = {"error": str(exc)}

    network = False
    try:
        network = bool(controller.network_evidence_available())
    except Exception:
        network = bool(of.get("connected")) and (of.get("backend") or of.get("configured_backend")) not in {
            "mock",
            None,
            "",
        }

    scorer: dict[str, Any] = {}
    try:
        from sdn_its.ai.live_scorer import get_live_scorer

        scorer = get_live_scorer().status()
    except Exception:
        pass

    exp_a = load_exp_a()
    last_trace = None
    traces = getattr(controller, "event_trace", None) or []
    if traces:
        last_trace = traces[-1]

    # Prefer live OF; fall back to last Exp A summary for Outcome/Traffic
    temp_arm = None
    if exp_a and isinstance(exp_a.get("arms"), list):
        for arm in exp_a["arms"]:
            if arm.get("arm") == "temporary":
                temp_arm = arm
                break

    traffic = {
        "source": "exp_a" if (exp_a and exp_a.get("network_evidence")) else "unavailable",
        "attack_delivery_ratio": None,
        "legit_delivery_ratio": None,
        "packetin_per_s": None,
        "note": "Run scripts/run_exp_a.ps1 (WSL) for data-plane ratios. PacketIn/s needs Ryu.",
    }
    if temp_arm:
        during = (temp_arm.get("traffic") or {}).get("during") or temp_arm.get("traffic") or {}
        traffic.update(
            {
                "attack_delivery_ratio": during.get("attack_delivery_ratio"),
                "legit_delivery_ratio": during.get("legit_delivery_ratio"),
                "packetin_per_s": during.get("packetin_per_s"),
                "source": "exp_a" if exp_a.get("network_evidence") else "exp_a_dry_run",
            }
        )

    fusion = getattr(controller, "last_fusion", None) or (last_trace or {}).get("fusion")
    detection = {
        "model_mode": scorer.get("mode"),
        "model_loaded": scorer.get("loaded"),
        "prediction": (last_trace or {}).get("prediction"),
        "ground_truth": (last_trace or {}).get("ground_truth"),
        "window_id": (last_trace or {}).get("telemetry_window_id"),
        "inference_id": (last_trace or {}).get("inference_id"),
        "baseline_prediction": "RE_threshold_aux",
        "confidence": None,
        "infer_calls": (getattr(controller, "stats", {}) or {}).get("infer_calls"),
        "fusion": fusion,
        "physical_context": (fusion or {}).get("physical_context"),
        "recommended_action": (fusion or {}).get("recommended_action"),
        "reason_codes": (fusion or {}).get("reason_codes"),
    }
    try:
        from sdn_its.camera.store import get_camera_store

        cam_snap = get_camera_store().snapshot()
    except Exception:
        cam_snap = None

    last_mods = list(of.get("last_mods") or [])
    last_ok = next((m for m in reversed(last_mods) if m.get("ok")), last_mods[-1] if last_mods else None)
    actuation = {
        "network_evidence": network,
        "of_backend": of.get("configured_backend") or of.get("backend"),
        "of_connected": bool(of.get("connected")),
        "requested_rule": (last_ok or {}).get("flow") or (last_ok or {}).get("of_action"),
        "switch_ack": (last_ok or {}).get("switch_ack") or (last_ok or {}).get("ok"),
        "rule_cookie": (last_ok or {}).get("cookie"),
        "verified_in_flow_dump": (last_ok or {}).get("verified_in_flow_dump"),
        "install_ms": (last_ok or {}).get("install_ms") or of.get("last_install_ms"),
        "flow_mods": of.get("flow_mods"),
        "bridges": of.get("bridges") or {},
        "greyed": not network,
        "banner": None if network else "NO NETWORK EVIDENCE",
    }
    if not network and temp_arm and exp_a and exp_a.get("network_evidence"):
        # File evidence from last lab run (not live)
        act = temp_arm.get("actuation") or {}
        actuation.update(
            {
                "from_exp_a_file": True,
                "requested_rule": act.get("rule"),
                "switch_ack": act.get("switch_ack"),
                "verified_in_flow_dump": act.get("verified_in_flow_dump"),
                "install_ms": act.get("install_ms"),
                "greyed": False,
                "banner": "From Exp A metrics file (not live OF session)",
                "network_evidence": True,
            }
        )
        network = True

    outcome = {
        "network_evidence": network,
        "greyed": not network,
        "banner": None if network else "NO NETWORK EVIDENCE",
        "attack_reduction_pct": None,
        "legitimate_delivery_ratio": None,
        "sla_violation": None,
        "rollback_success": None,
        "recovery_ms": None,
    }
    if temp_arm:
        oc = temp_arm.get("outcome") or {}
        if exp_a and exp_a.get("network_evidence"):
            outcome.update(
                {
                    "attack_reduction_pct": oc.get("attack_reduction_pct"),
                    "legitimate_delivery_ratio": oc.get("legitimate_delivery_ratio"),
                    "sla_violation": oc.get("sla_violation"),
                    "rollback_success": oc.get("rollback_success"),
                    "recovery_ms": oc.get("recovery_ms"),
                    "greyed": False,
                    "network_evidence": True,
                    "banner": None,
                    "source": "exp_a",
                }
            )

    return {
        "network_evidence": network,
        "traffic": traffic,
        "detection": detection,
        "actuation": actuation,
        "outcome": outcome,
        "exp_a": {
            "loaded": exp_a is not None,
            "dry_run": bool((exp_a or {}).get("dry_run")),
            "network_evidence": bool((exp_a or {}).get("network_evidence")),
            "summary": (exp_a or {}).get("summary"),
            "generated_at": (exp_a or {}).get("generated_at"),
        },
        "last_trace": last_trace,
        "camera": cam_snap,
        "fusion": fusion,
    }
