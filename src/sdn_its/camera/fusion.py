"""Rule-based multimodal fusion: SDN prediction × physical camera context.

Explainable first — not a single opaque neural net.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FusionDecision:
    network_prediction: str
    physical_context: str
    final_risk: str  # low | medium | high | critical
    recommended_action: str
    # observe | rate_limit | temporary_drop | preserve_rush_hour | protect_safety
    reason_codes: list[str] = field(default_factory=list)
    policy_attack_type: str | None = None  # label fed into PolicyEngine after fusion
    cooldown_seconds: float | None = None
    false_positive_corrected: bool = False
    # True only when network said anomaly but physical context corrected to preserve
    safety_critical: bool = False
    explain: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FusionEngine:
    """Join network alert features with edge camera aggregate."""

    def fuse(
        self,
        *,
        network_prediction: str,
        physical: dict[str, Any],
        source_dominance: float | None = None,
        distributed_sources: bool | None = None,
        packet_in_delta_pct: float | None = None,
    ) -> FusionDecision:
        net = network_prediction or "Normal"
        phys = str(physical.get("physical_label") or "unknown")
        is_vc = bool(physical.get("is_vehicle_count") or physical.get("vehicle_count_is_real"))
        vehicles = int(physical.get("vehicle_count") or 0) if is_vc else 0
        queue = float(physical.get("queue_length_m") or 0.0) if is_vc else 0.0
        band = str(physical.get("activity_band") or "unknown")
        ped = bool(physical.get("pedestrian_present"))
        incident = bool(physical.get("incident"))
        stale = bool(physical.get("stale"))
        analytics_valid = physical.get("analytics_valid")
        if analytics_valid is None:
            analytics_valid = not stale
        dominance = 0.5 if source_dominance is None else float(source_dominance)
        distributed = bool(distributed_sources) if distributed_sources is not None else dominance < 0.45
        pin = packet_in_delta_pct

        reasons: list[str] = []
        if pin is not None and pin >= 100:
            reasons.append("HIGH_PACKET_IN")
        if is_vc and (vehicles >= 25 or queue >= 40 or phys == "rush_hour"):
            reasons.append("HIGH_PHYSICAL_TRAFFIC")
        elif (not is_vc) and (band == "high" or phys == "rush_hour"):
            reasons.append("HIGH_VISUAL_ACTIVITY_PROXY")
        if is_vc and phys in {"stable", "unknown"} and vehicles < 12:
            reasons.append("PHYSICAL_STABLE")
        elif (not is_vc) and band == "low" and phys in {"stable", "unknown"}:
            reasons.append("PHYSICAL_STABLE")
        if not is_vc and physical.get("visual_activity"):
            reasons.append("VISUAL_ACTIVITY_PROXY_NOT_DETECTOR")
        if distributed:
            reasons.append("DISTRIBUTED_SOURCES")
        if dominance >= 0.7:
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
            rush_phys = phys in {"rush_hour", "elevated", "mixed_busy"} and vehicles >= 12
        else:
            rush_phys = phys in {"rush_hour", "elevated", "mixed_busy"} and band in {"high", "medium"}

        # Scenario C first: physical rush/incident BUT a dominant attacker → isolate source only
        if net_anom and rush_phys and dominance >= 0.7 and not stale:
            return FusionDecision(
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

        # Safety overlay when NO dominant attacker — preserve junction traffic
        if incident or (ped and phys in {"rush_hour", "mixed_busy", "elevated", "incident"}):
            return FusionDecision(
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

        # Network says flood, camera agrees with congestion + distributed → preserve
        if net_anom and rush_phys and distributed and not stale:
            return FusionDecision(
                network_prediction=net,
                physical_context=phys,
                final_risk="medium",
                recommended_action="preserve_rush_hour",
                reason_codes=reasons,
                policy_attack_type="RushHour_Burst",
                cooldown_seconds=0.0,
                false_positive_corrected=net != "RushHour_Burst",
                safety_critical=False,
                explain="Packet growth co-occurs with physical congestion and distributed sources → legitimate surge.",
            )

        # Network says rush hour by label, but camera stable + single source → correct to contain
        if net == "RushHour_Burst" and phys == "stable" and dominance >= 0.65 and not stale:
            return FusionDecision(
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

        # Network anomaly + camera stable + single source → contain
        if net_anom and phys == "stable" and dominance >= 0.55 and not stale:
            action = "temporary_drop" if net == "DDoS_PacketIn_Flood" else "rate_limit"
            return FusionDecision(
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

        # Soft path when camera stale / analytics invalid
        if net_anom and (stale or analytics_valid is False):
            return FusionDecision(
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
            return FusionDecision(
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
            return FusionDecision(
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

        return FusionDecision(
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
