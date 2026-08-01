"""Request/response schema helpers for the REST API."""

from __future__ import annotations

from typing import Any

REQUIRED_ALERT_FIELDS = ("attack_type", "dpid")


def validate_anomaly_alert(data: Any) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "Payload must be a JSON object"
    for field in REQUIRED_ALERT_FIELDS:
        if field not in data:
            return False, "Invalid payload format. Required: 'attack_type', 'dpid'"
    return True, ""


def status_payload(controller) -> dict[str, Any]:
    import time

    uptime_sec = time.time() - controller.stats["start_time"]
    runtime = getattr(controller, "runtime_settings", {}) or {}
    tau = runtime.get("tau")
    try:
        from sdn_its.ai.live_scorer import get_live_scorer

        tau = get_live_scorer().status().get("tau", tau)
    except Exception:
        pass
    return {
        "status": "ONLINE",
        "service": "SDN ITS AI Resilience Controller",
        "uptime_seconds": round(uptime_sec, 1),
        "stats": controller.stats,
        "openflow": getattr(controller, "openflow_status", lambda: {})(),
        "active_mitigations_count": len(controller.flow_mgr.active_rules),
        "tau": tau,
        "role_mode": runtime.get("role_mode", "research"),
        "theme": runtime.get("theme", "light"),
        "dataset_mode": runtime.get("dataset_mode", "sample"),
    }
