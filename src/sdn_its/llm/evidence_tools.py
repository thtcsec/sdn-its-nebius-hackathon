"""Grounded evidence tools for cyber–physical investigation.

Tools execute real application logic over incident context / fixture windows.
They never invent live RTSP inference or PacketIn switch counters.
Camera fields are treated as same-zone metadata (synthetic or previously derived).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

TOOL_NAMES = (
    "retrieve_network_telemetry",
    "inspect_camera_metadata",
    "check_physical_evidence_quality",
    "compare_temporal_windows",
    "identify_contradictions",
    "escalate_human_review",
)


@dataclass
class ToolResult:
    tool: str
    ok: bool
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    evidence_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceBundle:
    """Mutable investigation state filled by tools."""

    incident_id: str
    network_prediction: str
    include_camera: bool = True
    telemetry: dict[str, Any] = field(default_factory=dict)
    camera: dict[str, Any] = field(default_factory=dict)
    prior_windows: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    physical_sufficient: bool | None = None
    physical_quality: dict[str, Any] = field(default_factory=dict)
    contradictions: list[str] = field(default_factory=list)
    human_escalation_requested: bool = False
    uncertainties: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "network_prediction": self.network_prediction,
            "include_camera": self.include_camera,
            "telemetry": self.telemetry,
            "camera": self.camera if self.include_camera else {"ablation": "camera_disabled"},
            "prior_windows": self.prior_windows,
            "tool_results": [t.to_dict() for t in self.tool_results],
            "physical_sufficient": self.physical_sufficient,
            "physical_quality": self.physical_quality,
            "contradictions": list(self.contradictions),
            "human_escalation_requested": self.human_escalation_requested,
            "uncertainties": list(self.uncertainties),
            "camera_context_note": (
                "Camera fields are same-zone metadata (fixture/synthetic or derived). "
                "Not claimed as live RTSP/YOLO inference in the judge path."
            ),
        }


def assess_physical_quality(camera: dict[str, Any] | None) -> dict[str, Any]:
    """Deterministic physical-evidence quality check (no model)."""
    cam = dict(camera or {})
    stream_ok = bool(cam.get("stream_available", True))
    analytics_ok = bool(cam.get("analytics_valid", False))
    stale = bool(cam.get("stale", False))
    tracks = cam.get("visible_vehicle_tracks")
    has_count = tracks is not None and bool(cam.get("is_vehicle_count") or cam.get("vehicle_count_is_real"))
    label = str(cam.get("physical_label") or "unknown")
    band = str(cam.get("activity_band") or "unknown")

    reasons: list[str] = []
    if not stream_ok:
        reasons.append("stream_unavailable")
    if not analytics_ok:
        reasons.append("analytics_invalid")
    if stale:
        reasons.append("stale_context")
    if label in {"", "unknown", "none"} and band in {"", "unknown", "none"}:
        reasons.append("label_unknown")
    if not has_count and not bool(cam.get("incident")) and not bool(cam.get("pedestrian_present")):
        reasons.append("no_usable_physical_signal")

    sufficient = stream_ok and analytics_ok and not stale and "no_usable_physical_signal" not in reasons
    # Safety-critical flags remain usable even if counts missing
    if bool(cam.get("incident")) or bool(cam.get("pedestrian_present")):
        if stream_ok and not stale:
            sufficient = True
            reasons = [r for r in reasons if r != "no_usable_physical_signal"]

    return {
        "sufficient": sufficient,
        "stream_available": stream_ok,
        "analytics_valid": analytics_ok,
        "stale": stale,
        "has_vehicle_count": has_count,
        "physical_label": label,
        "activity_band": band,
        "reasons": reasons,
        "context_source": cam.get("context_source") or "unspecified",
    }


def identify_uncertainty(bundle: EvidenceBundle) -> list[str]:
    """DETECT → list open questions before tool use."""
    u: list[str] = []
    net = bundle.network_prediction
    tel = bundle.telemetry
    pin = tel.get("packet_in_delta_pct")
    if pin is None:
        u.append("missing_packet_in_delta")
    if net in {"DDoS_PacketIn_Flood", "LOFT_LowRate_Attack", "RushHour_Burst"}:
        u.append("anomaly_requires_physical_context")
    if bundle.include_camera:
        q = assess_physical_quality(bundle.camera)
        if not q["sufficient"]:
            u.append("physical_evidence_insufficient")
        if q["stale"] or not q["analytics_valid"]:
            u.append("camera_stale_or_invalid")
        label = q["physical_label"]
        if net.startswith("DDoS") or net.startswith("LOFT"):
            if label in {"rush_hour", "congested", "busy"}:
                u.append("possible_false_positive_vs_congestion")
        if net == "RushHour_Burst" and label in {"quiet", "empty", "stable"}:
            u.append("rush_label_vs_quiet_camera")
    else:
        u.append("camera_ablation_disabled")
    if not bundle.prior_windows:
        u.append("no_temporal_baseline_yet")
    bundle.uncertainties = u
    return u


def _tool_retrieve_network(bundle: EvidenceBundle, args: dict[str, Any]) -> ToolResult:
    tel = dict(bundle.telemetry)
    pin = tel.get("packet_in_delta_pct")
    dom = tel.get("source_dominance")
    dist = tel.get("distributed_sources")
    notes = [
        f"window={tel.get('window_id') or 'current'}",
        f"packet_in_delta_pct={pin}",
        f"source_dominance={dom}",
        f"distributed_sources={dist}",
        f"network_prediction={bundle.network_prediction}",
    ]
    summary = (
        f"Telemetry window retrieved for {bundle.network_prediction}: "
        f"ΔPacketIn={pin}% dominance={dom} distributed={dist}"
    )
    return ToolResult(
        tool="retrieve_network_telemetry",
        ok=True,
        summary=summary,
        data={"telemetry": tel, "network_prediction": bundle.network_prediction},
        evidence_notes=notes,
    )


def _tool_inspect_camera(bundle: EvidenceBundle, args: dict[str, Any]) -> ToolResult:
    if not bundle.include_camera:
        return ToolResult(
            tool="inspect_camera_metadata",
            ok=False,
            summary="Camera tools disabled for this ablation arm (network-only).",
            data={"ablation": "camera_disabled"},
            evidence_notes=["camera_ablation_disabled"],
        )
    cam = dict(bundle.camera)
    notes = [
        f"physical_label={cam.get('physical_label')}",
        f"activity_band={cam.get('activity_band')}",
        f"tracks={cam.get('visible_vehicle_tracks')}",
        f"queue_m={cam.get('queue_length_proxy_m')}",
        f"context_source={cam.get('context_source')}",
        "not_live_rtsp_claim",
    ]
    return ToolResult(
        tool="inspect_camera_metadata",
        ok=True,
        summary=(
            f"Same-zone camera metadata: label={cam.get('physical_label')} "
            f"band={cam.get('activity_band')} tracks={cam.get('visible_vehicle_tracks')} "
            f"(metadata only; not live RTSP inference)"
        ),
        data={"camera": cam},
        evidence_notes=notes,
    )


def _tool_check_quality(bundle: EvidenceBundle, args: dict[str, Any]) -> ToolResult:
    if not bundle.include_camera:
        q = {"sufficient": False, "reasons": ["camera_ablation_disabled"]}
        bundle.physical_sufficient = False
        bundle.physical_quality = q
        return ToolResult(
            tool="check_physical_evidence_quality",
            ok=True,
            summary="Physical evidence unavailable (camera ablation).",
            data=q,
            evidence_notes=["physical_insufficient", "camera_ablation_disabled"],
        )
    q = assess_physical_quality(bundle.camera)
    bundle.physical_quality = q
    bundle.physical_sufficient = bool(q["sufficient"])
    notes = list(q.get("reasons") or [])
    notes.append("physical_sufficient" if q["sufficient"] else "physical_insufficient")
    return ToolResult(
        tool="check_physical_evidence_quality",
        ok=True,
        summary=(
            "Physical evidence SUFFICIENT for containment decisions."
            if q["sufficient"]
            else f"Physical evidence INSUFFICIENT ({', '.join(q.get('reasons') or [])}). Prefer observe over model escalation."
        ),
        data=q,
        evidence_notes=notes,
    )


def _tool_compare_windows(bundle: EvidenceBundle, args: dict[str, Any]) -> ToolResult:
    current = dict(bundle.telemetry)
    priors = list(bundle.prior_windows or [])
    if not priors:
        # Synthesize a calm prior from fixture convention when absent (declared synthetic)
        priors = [
            {
                "window_id": "prior_synthetic_baseline",
                "packet_in_delta_pct": max(0.0, float(current.get("packet_in_delta_pct") or 0) * 0.25),
                "source_dominance": min(0.35, float(current.get("source_dominance") or 0.2)),
                "distributed_sources": True,
                "context_source": "synthetic_temporal_baseline",
            }
        ]
        bundle.prior_windows = priors
    cur_pin = float(current.get("packet_in_delta_pct") or 0)
    base_pin = float(priors[-1].get("packet_in_delta_pct") or 0)
    delta = cur_pin - base_pin
    rising = delta >= 15.0
    data = {
        "current": current,
        "prior": priors[-1],
        "delta_packet_in_pct_points": delta,
        "surge_vs_baseline": rising,
        "baseline_note": "Prior window may be fixture-synthesized when history absent.",
    }
    return ToolResult(
        tool="compare_temporal_windows",
        ok=True,
        summary=f"Temporal compare: ΔPacketIn vs prior = {delta:.1f} pp; surge={rising}",
        data=data,
        evidence_notes=[f"temporal_delta_pp={delta:.1f}", f"surge={rising}"],
    )


def _tool_contradictions(bundle: EvidenceBundle, args: dict[str, Any]) -> ToolResult:
    contradictions: list[str] = []
    net = bundle.network_prediction
    cam = bundle.camera if bundle.include_camera else {}
    label = str(cam.get("physical_label") or "unknown")
    band = str(cam.get("activity_band") or "unknown")
    pin = float((bundle.telemetry or {}).get("packet_in_delta_pct") or 0)
    q = bundle.physical_quality or assess_physical_quality(cam if bundle.include_camera else {})

    if bundle.include_camera and q.get("sufficient"):
        if net in {"DDoS_PacketIn_Flood", "LOFT_LowRate_Attack"} and label in {
            "rush_hour",
            "congested",
            "busy",
        }:
            contradictions.append("network_attack_label_vs_rush_physical")
        if net == "RushHour_Burst" and label in {"quiet", "empty", "stable"} and pin > 40:
            contradictions.append("rush_network_vs_quiet_physical")
        if net == "Normal" and bool(cam.get("incident")):
            contradictions.append("quiet_network_vs_physical_incident")
        if band in {"high", "rush"} and net.startswith("DDoS") and float(cam.get("queue_length_proxy_m") or 0) > 30:
            contradictions.append("ddos_vs_long_queue")
    elif bundle.include_camera and not q.get("sufficient"):
        contradictions.append("cannot_corroborate_physical_context")

    bundle.contradictions = contradictions
    return ToolResult(
        tool="identify_contradictions",
        ok=True,
        summary=(
            "No hard contradictions flagged."
            if not contradictions
            else "Contradictions: " + "; ".join(contradictions)
        ),
        data={"contradictions": contradictions, "network_prediction": net, "physical_label": label},
        evidence_notes=contradictions or ["no_hard_contradiction"],
    )


def _tool_escalate(bundle: EvidenceBundle, args: dict[str, Any]) -> ToolResult:
    reason = str(args.get("reason") or "investigator_requested_human_review")
    bundle.human_escalation_requested = True
    return ToolResult(
        tool="escalate_human_review",
        ok=True,
        summary=f"Human review requested: {reason}",
        data={"reason": reason, "recommended_interim_action": "observe"},
        evidence_notes=["human_escalation", reason],
    )


_HANDLERS: dict[str, Callable[[EvidenceBundle, dict[str, Any]], ToolResult]] = {
    "retrieve_network_telemetry": _tool_retrieve_network,
    "inspect_camera_metadata": _tool_inspect_camera,
    "check_physical_evidence_quality": _tool_check_quality,
    "compare_temporal_windows": _tool_compare_windows,
    "identify_contradictions": _tool_contradictions,
    "escalate_human_review": _tool_escalate,
}


def list_tools(*, include_camera: bool = True) -> list[dict[str, str]]:
    descs = {
        "retrieve_network_telemetry": "Retrieve recent network telemetry window for this incident.",
        "inspect_camera_metadata": "Inspect same-zone camera-derived metadata (not live RTSP claim).",
        "check_physical_evidence_quality": "Check whether physical evidence is stale, invalid, or unavailable.",
        "compare_temporal_windows": "Compare current telemetry to a prior temporal baseline window.",
        "identify_contradictions": "Flag contradictions between network labels and physical conditions.",
        "escalate_human_review": "Escalate to human review; interim action should remain observe.",
    }
    names = list(TOOL_NAMES)
    if not include_camera:
        names = [n for n in names if n not in {"inspect_camera_metadata", "check_physical_evidence_quality"}]
    return [{"name": n, "description": descs[n]} for n in names]


def execute_tool(name: str, bundle: EvidenceBundle, args: dict[str, Any] | None = None) -> ToolResult:
    handler = _HANDLERS.get(name)
    if handler is None:
        result = ToolResult(
            tool=name,
            ok=False,
            summary=f"Unknown tool: {name}",
            data={},
            evidence_notes=["unknown_tool"],
        )
    else:
        result = handler(bundle, dict(args or {}))
    bundle.tool_results.append(result)
    return result


def default_tool_plan(bundle: EvidenceBundle) -> list[str]:
    """Deterministic planner used offline / when model does not choose tools."""
    # Order prioritizes quality + contradiction checks inside the default tool budget.
    plan = ["retrieve_network_telemetry"]
    if bundle.include_camera:
        plan.extend(
            [
                "inspect_camera_metadata",
                "check_physical_evidence_quality",
                "identify_contradictions",
                "compare_temporal_windows",
            ]
        )
    else:
        plan.extend(["compare_temporal_windows", "identify_contradictions"])
    uncertainties = identify_uncertainty(bundle)
    if "physical_evidence_insufficient" in uncertainties or "camera_ablation_disabled" in uncertainties:
        plan.append("escalate_human_review")
    # Cap later by multi_step max_tools
    return plan
