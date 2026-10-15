"""Rule-based cyber–physical fusion: SDN/RSU network prediction × same-zone camera context.

Camera is a physical-context sensor for mitigation decisions (cyber–physical consistency),
not a DDoS detector. Network evidence remains primary; camera must not override it.
Explainable first — not a single opaque neural net.
Thresholds are injectable for sensitivity studies.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from sdn_its.llm.input_sanitize import safe_bool, safe_float, safe_int, sanitize_camera, sanitize_telemetry


@dataclass
class FusionThresholds:
    """Handcrafted cutoffs — must be swept; not calibrated ROC points."""

    dominance_mixed_isolate: float = 0.70  # rush + attack → temporary_drop
    dominance_label_disagree: float = 0.65  # RushHour label but stable cam
    dominance_stable_contain: float = 0.55  # anomaly + stable → contain
    distributed_below: float = 0.45
    tracks_high: int = 25
    tracks_rush_min: int = 12
    queue_high_m: float = 40.0
    pin_high_pct: float = 100.0


@dataclass
class FusionDecision:
    network_prediction: str
    physical_context: str
    final_risk: str  # low | medium | high | critical
    recommended_action: str
    # observe | rate_limit | temporary_drop | preserve_rush_hour | protect_safety
    reason_codes: list[str] = field(default_factory=list)
    policy_attack_type: str | None = None
    cooldown_seconds: float | None = None
    false_positive_corrected: bool = False
    safety_critical: bool = False
    explain: str = ""
    thresholds_used: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FusionEngine:
    """Join network alert features with edge camera aggregate."""

    def __init__(self, thresholds: FusionThresholds | None = None):
        self.th = thresholds or FusionThresholds()

    def fuse(
        self,
        *,
        network_prediction: str,
        physical: dict[str, Any],
        source_dominance: float | None = None,
        distributed_sources: bool | None = None,
        packet_in_delta_pct: float | None = None,
        telemetry: dict[str, Any] | None = None,
    ) -> FusionDecision:
        th = self.th
        thr_meta = asdict(th)
        net = network_prediction or "Normal"

        # Untrusted inputs: sanitize camera + optional full telemetry blob
        physical, cam_issues = sanitize_camera(physical)
        tel_issues: list[str] = []
        if telemetry is not None:
            tel_clean, tel_issues = sanitize_telemetry(telemetry)
            if source_dominance is None:
                source_dominance = tel_clean.get("source_dominance")
            if distributed_sources is None:
                distributed_sources = tel_clean.get("distributed_sources")
            if packet_in_delta_pct is None:
                packet_in_delta_pct = tel_clean.get("packet_in_delta_pct")
            if tel_clean.get("_telemetry_unreliable"):
                tel_issues = list(tel_clean.get("_sanitize_issues") or tel_issues)

        # Coerce explicit kwargs safely (callers may still pass raw strings)
        dominance_parsed = safe_float(source_dominance, default=None, min_v=0.0, max_v=1.0)
        if source_dominance is not None and dominance_parsed is None:
            tel_issues.append("invalid_source_dominance")
        pin_parsed = safe_float(packet_in_delta_pct, default=None, min_v=-100.0, max_v=10_000.0)
        if packet_in_delta_pct is not None and pin_parsed is None:
            tel_issues.append("invalid_packet_in_delta_pct")
        if pin_parsed is not None and pin_parsed < 0:
            tel_issues.append("negative_packet_in_delta_pct")
            pin_parsed = None
        dist_parsed = safe_bool(distributed_sources, default=None)
        if distributed_sources is not None and dist_parsed is None:
            tel_issues.append("invalid_distributed_sources")

        unreliable = bool(tel_issues) or bool(physical.get("_telemetry_unreliable"))

        phys = str(physical.get("physical_label") or "unknown")
        is_vc = bool(
            physical.get("is_vehicle_count")
            or physical.get("vehicle_count_is_real")
            or physical.get("visible_vehicle_tracks") is not None
        )
        vehicles = (
            safe_int(
                physical.get("visible_vehicle_tracks")
                if physical.get("visible_vehicle_tracks") is not None
                else physical.get("vehicle_count"),
                default=0,
                min_v=0,
                max_v=100_000,
            )
            or 0
        ) if is_vc else 0
        queue = (
            safe_float(
                physical.get("queue_length_proxy_m")
                if physical.get("queue_length_proxy_m") is not None
                else physical.get("queue_length_m"),
                default=0.0,
                min_v=0.0,
                max_v=10_000.0,
            )
            or 0.0
        ) if is_vc else 0.0
        band = str(physical.get("activity_band") or "unknown")
        ped = bool(safe_bool(physical.get("pedestrian_present"), default=False))
        incident = bool(safe_bool(physical.get("incident"), default=False))
        stale = bool(safe_bool(physical.get("stale"), default=False))
        analytics_valid = safe_bool(physical.get("analytics_valid"), default=None)
        if analytics_valid is None:
            analytics_valid = not stale
        dominance = 0.5 if dominance_parsed is None else dominance_parsed
        distributed = (
            dist_parsed
            if dist_parsed is not None
            else dominance < th.distributed_below
        )
        pin = pin_parsed

        reasons: list[str] = list(cam_issues)
        if tel_issues:
            reasons.extend(tel_issues)
            reasons.append("TELEMETRY_UNRELIABLE")

        # Fail closed: unreliable telemetry → observe only (never crash / never contain)
        if unreliable:
            return FusionDecision(
                network_prediction=net,
                physical_context=phys,
                final_risk="low",
                recommended_action="observe",
                reason_codes=reasons + ["FAIL_CLOSED_UNTRUSTED_TELEMETRY"],
                policy_attack_type=None,
                cooldown_seconds=0.0,
                false_positive_corrected=False,
                safety_critical=False,
                explain=(
                    "Telemetry or numeric fields failed validation (NaN/non-numeric/unreliable). "
                    "Observe only — no containment from untrusted inputs."
                ),
                thresholds_used=thr_meta,
            )

        if pin is not None and pin >= th.pin_high_pct:
            reasons.append("HIGH_PACKET_IN")
        if is_vc and (vehicles >= th.tracks_high or queue >= th.queue_high_m or phys == "rush_hour"):
            reasons.append("HIGH_PHYSICAL_TRAFFIC")
        elif (not is_vc) and (band == "high" or phys == "rush_hour"):
            reasons.append("HIGH_VISUAL_ACTIVITY_PROXY")
        if is_vc and phys in {"stable", "unknown"} and vehicles < th.tracks_rush_min:
            reasons.append("PHYSICAL_STABLE")
        elif (not is_vc) and band == "low" and phys in {"stable", "unknown"}:
            reasons.append("PHYSICAL_STABLE")
        if not is_vc and physical.get("visual_activity"):
            reasons.append("VISUAL_ACTIVITY_PROXY_NOT_DETECTOR")
        if distributed:
            reasons.append("DISTRIBUTED_SOURCES")
        if dominance >= th.dominance_mixed_isolate:
            reasons.append("SINGLE_SOURCE_DOMINANCE")
        if ped:
            reasons.append("PEDESTRIAN_PRESENT")
        if incident:
            reasons.append("INCIDENT_DETECTED")
        if stale:
            reasons.append("CAMERA_CONTEXT_STALE")
        if analytics_valid is False:
            reasons.append("ANALYTICS_INVALID")

        net_anom = net in {"DDoS_PacketIn_Flood", "LOFT_LowRate_Attack"} or (
            net not in {"Normal", "RushHour_Burst", None, ""}
        )
        if is_vc:
            rush_phys = phys in {"rush_hour", "elevated", "mixed_busy"} and vehicles >= th.tracks_rush_min
        else:
            rush_phys = phys in {"rush_hour", "elevated", "mixed_busy"} and band in {"high", "medium"}

        def _dec(**kwargs: Any) -> FusionDecision:
            kwargs.setdefault("thresholds_used", thr_meta)
            return FusionDecision(**kwargs)

        if net_anom and rush_phys and dominance >= th.dominance_mixed_isolate and not stale:
            return _dec(
                network_prediction=net,
                physical_context=phys,
                final_risk="high",
                recommended_action="temporary_drop",
                reason_codes=reasons + ["MIXED_RUSH_AND_ATTACK"],
                policy_attack_type="DDoS_PacketIn_Flood",
                cooldown_seconds=15.0,
                false_positive_corrected=False,
                safety_critical=bool(ped or incident),
                explain=(
                    "Rush-hour/incident camera context + dominant attacker source → "
                    "isolate that source only; keep junction/camera streams prioritized."
                ),
            )

        if incident or (ped and phys in {"rush_hour", "mixed_busy", "elevated", "incident"}):
            # Only if not already handled as dominant attacker above
            if dominance < th.dominance_mixed_isolate:
                return _dec(
                    network_prediction=net,
                    physical_context=phys,
                    final_risk="critical" if incident else "medium",
                    recommended_action="protect_safety",
                    reason_codes=reasons or ["SAFETY_CRITICAL"],
                    policy_attack_type="RushHour_Burst" if net != "LOFT_LowRate_Attack" else net,
                    cooldown_seconds=0.0,
                    false_positive_corrected=net in {"DDoS_PacketIn_Flood", "LOFT_LowRate_Attack"},
                    safety_critical=True,
                    explain=(
                        "Camera marks pedestrian/incident without a dominant attacker — "
                        "preserve junction traffic and prioritize safety camera streams."
                    ),
                )

        # Rush/congestion without isolate-level dominance → preserve.
        # Mid-dominance must NOT fall through to NETWORK_ONLY DROP (that erased threshold sensitivity).
        if net_anom and rush_phys and dominance < th.dominance_mixed_isolate and not stale:
            return _dec(
                network_prediction=net,
                physical_context=phys,
                final_risk="medium",
                recommended_action="preserve_rush_hour",
                reason_codes=reasons + (["DISTRIBUTED_SOURCES"] if distributed else ["RUSH_BELOW_ISOLATE_THRESHOLD"]),
                policy_attack_type="RushHour_Burst",
                cooldown_seconds=0.0,
                false_positive_corrected=net != "RushHour_Burst",
                safety_critical=False,
                explain=(
                    "Packet growth co-occurs with physical congestion below isolate dominance "
                    "→ treat as legitimate surge (preserve)."
                ),
            )

        if net == "RushHour_Burst" and phys == "stable" and dominance >= th.dominance_label_disagree and not stale:
            return _dec(
                network_prediction=net,
                physical_context=phys,
                final_risk="high",
                recommended_action="temporary_drop",
                reason_codes=reasons + ["LABEL_CAMERA_DISAGREE"],
                policy_attack_type="DDoS_PacketIn_Flood",
                cooldown_seconds=15.0,
                false_positive_corrected=False,
                safety_critical=False,
                explain="Scenario/model labeled rush hour, but camera is stable and one source dominates → treat as attack.",
            )

        if net_anom and phys == "stable" and dominance >= th.dominance_stable_contain and not stale:
            action = "temporary_drop" if net == "DDoS_PacketIn_Flood" else "rate_limit"
            return _dec(
                network_prediction=net,
                physical_context=phys,
                final_risk="high",
                recommended_action=action,
                reason_codes=reasons,
                policy_attack_type=net if net != "Normal" else "DDoS_PacketIn_Flood",
                cooldown_seconds=15.0,
                false_positive_corrected=False,
                safety_critical=False,
                explain="Network anomaly without matching physical traffic → isolate dominant source temporarily.",
            )

        # Stable scene but dominance below contain threshold → soft action (not hard DROP).
        if net_anom and phys == "stable" and dominance < th.dominance_stable_contain and not stale:
            return _dec(
                network_prediction=net,
                physical_context=phys,
                final_risk="medium",
                recommended_action="rate_limit",
                reason_codes=reasons + ["STABLE_BELOW_CONTAIN_THRESHOLD"],
                policy_attack_type="LOFT_LowRate_Attack",
                cooldown_seconds=12.0,
                false_positive_corrected=False,
                safety_critical=False,
                explain=(
                    "Stable camera + anomaly but source dominance below contain threshold → "
                    "soft rate-limit (avoids false contain)."
                ),
            )

        if net_anom and (stale or analytics_valid is False):
            return _dec(
                network_prediction=net,
                physical_context=phys,
                final_risk="medium",
                recommended_action="rate_limit",
                reason_codes=reasons,
                policy_attack_type="LOFT_LowRate_Attack",
                cooldown_seconds=12.0,
                false_positive_corrected=False,
                safety_critical=False,
                explain="Camera stale or analytics invalid — prefer soft rate-limit over hard DROP.",
            )

        if net == "RushHour_Burst":
            return _dec(
                network_prediction=net,
                physical_context=phys,
                final_risk="low",
                recommended_action="preserve_rush_hour",
                reason_codes=reasons or ["NETWORK_RUSH_LABEL"],
                policy_attack_type="RushHour_Burst",
                cooldown_seconds=0.0,
                false_positive_corrected=False,
                safety_critical=False,
                explain="Network rush-hour label with no contradicting physical evidence.",
            )

        if net_anom:
            return _dec(
                network_prediction=net,
                physical_context=phys,
                final_risk="medium",
                recommended_action="rate_limit" if net == "LOFT_LowRate_Attack" else "temporary_drop",
                reason_codes=reasons or ["NETWORK_ONLY"],
                policy_attack_type=net,
                cooldown_seconds=15.0,
                false_positive_corrected=False,
                safety_critical=False,
                explain="Fallback network-only policy (camera did not strongly confirm or deny).",
            )

        return _dec(
            network_prediction=net,
            physical_context=phys,
            final_risk="low",
            recommended_action="observe",
            reason_codes=reasons or ["NOMINAL"],
            policy_attack_type="Normal",
            cooldown_seconds=0.0,
            false_positive_corrected=False,
            safety_critical=False,
            explain="No mitigation required.",
        )
