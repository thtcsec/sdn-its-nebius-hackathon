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
    scorer_mode = None
    model_loaded = None
    preprocess_mode = None
    load_error = None
    try:
        from sdn_its.ai.live_scorer import get_live_scorer

        st = get_live_scorer().status()
        tau = st.get("tau", tau)
        scorer_mode = st.get("mode")
        model_loaded = st.get("loaded")
        preprocess_mode = st.get("preprocess_mode")
        load_error = st.get("load_error")
    except Exception:
        pass

    of: dict[str, Any] = {}
    try:
        of = controller.openflow_status(refresh=False)
    except Exception:
        of = getattr(controller, "openflow_status", lambda: {})()

    evidence = False
    try:
        evidence = bool(controller.network_evidence_available())
    except Exception:
        evidence = False
    controller.stats["network_evidence"] = evidence
    n_intended = len(controller.flow_mgr.active_rules)

    return {
        "status": "ONLINE",
        "service": "SDN ITS Reversible Mitigation Testbed",
        "uptime_seconds": round(uptime_sec, 1),
        "stats": controller.stats,
        "openflow": of,
        "active_mitigations_count": n_intended,  # legacy alias
        "intended_rules_count": n_intended,
        "of_rules_installed_total": int(controller.stats.get("of_rules_installed", 0)),
        "network_evidence": evidence,
        "latency_note": "Default /latency_cdf is policy_in_process ms — not network E2E",
        "tau": tau,
        "role_mode": runtime.get("role_mode", "research"),
        "theme": runtime.get("theme", "light"),
        "dataset_mode": runtime.get("dataset_mode", "sample"),
        "lab_mode": bool(runtime.get("lab_mode")),
        "scenario_override": (
            controller.allow_scenario_override()
            if hasattr(controller, "allow_scenario_override")
            else bool(runtime.get("scenario_override", True))
        ),
        "scorer_mode": scorer_mode,
        "model_loaded": model_loaded,
        "preprocess_mode": preprocess_mode,
        "load_error": load_error,
        "of_backend": of.get("configured_backend") or of.get("backend"),
    }
