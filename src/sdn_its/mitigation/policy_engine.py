"""Policy engine: map anomaly alerts (+ optional fusion) to Detect → Contain → Rollback."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .containment import ContainmentEngine


@dataclass
class MitigationResult:
    mitigation_status: str
    applied_rules: list[dict[str, Any]] = field(default_factory=list)
    false_positive_avoided: bool = False
    fusion: dict[str, Any] | None = None


class PolicyEngine:
    """Closed-loop mitigation policy matrix for ITS / V2X safety-aware response."""

    def __init__(self, containment: ContainmentEngine):
        self.containment = containment

    def apply(
        self,
        attack_type: str,
        dpid: str,
        src_ip: str = "10.0.0.15",
        dst_ip: str | None = None,
        cooldown: float = 30.0,
        *,
        fusion: dict[str, Any] | None = None,
    ) -> MitigationResult:
        applied: list[dict[str, Any]] = []
        fusion = fusion or {}
        action = fusion.get("recommended_action")
        # Fusion may remap the effective attack type
        effective = fusion.get("policy_attack_type") or attack_type
        if fusion.get("cooldown_seconds") is not None:
            cooldown = float(fusion["cooldown_seconds"])

        fp_corrected = bool(fusion.get("false_positive_corrected"))

        if action == "observe" or effective in {"Normal", None}:
            return MitigationResult("OBSERVE_ONLY", applied, fusion=fusion)

        if action == "protect_safety" or (fusion.get("safety_critical") and action == "preserve_rush_hour"):
            print(
                f"[Policy] Safety-critical physical context on DPID {dpid} "
                f"(pedestrian/incident). Preserving junction traffic."
            )
            return MitigationResult(
                "PROTECTED_SAFETY_CRITICAL",
                applied,
                false_positive_avoided=fp_corrected or attack_type in {"DDoS_PacketIn_Flood", "LOFT_LowRate_Attack"},
                fusion=fusion,
            )

        if action == "preserve_rush_hour" or effective == "RushHour_Burst":
            print(
                f"[Policy] Rush-hour / legitimate surge on DPID {dpid}. "
                "Preserving legitimate V2X flow integrity."
            )
            # Research FP metric only when fusion corrected an anomaly prediction
            return MitigationResult(
                "IGNORED_BENIGN_RUSH_HOUR",
                applied,
                false_positive_avoided=fp_corrected,
                fusion=fusion,
            )

        if action == "rate_limit" or effective == "LOFT_LowRate_Attack":
            rule = self.containment.create_rate_limit_rule(
                dpid=dpid, src_ip=src_ip, max_rate_kbps=500, priority=180, cooldown=cooldown
            )
            applied.append(rule.to_dict())
            return MitigationResult("CONTAINED_RATE_LIMITED", applied, fusion=fusion)

        if action == "temporary_drop" or effective == "DDoS_PacketIn_Flood":
            rule1 = self.containment.create_drop_rule(
                dpid=dpid, src_ip=src_ip, dst_ip=dst_ip, priority=200, cooldown=cooldown or 15.0
            )
            rule2 = self.containment.create_packet_in_throttle_rule(
                dpid=dpid, priority=250, cooldown=cooldown or 15.0
            )
            applied.extend([rule1.to_dict(), rule2.to_dict()])
            return MitigationResult("CONTAINED_DROP_AND_THROTTLE", applied, fusion=fusion)

        if effective == "RSU_Link_Fault":
            print(f"[Policy] RSU Link Fault on DPID {dpid}. Triggering path reroute event.")
            return MitigationResult("REROUTED_RSU_FAULT", applied, fusion=fusion)

        # Legacy label path without fusion action
        if attack_type == "DDoS_PacketIn_Flood":
            rule1 = self.containment.create_drop_rule(
                dpid=dpid, src_ip=src_ip, dst_ip=dst_ip, priority=200, cooldown=cooldown
            )
            rule2 = self.containment.create_packet_in_throttle_rule(
                dpid=dpid, priority=250, cooldown=cooldown
            )
            applied.extend([rule1.to_dict(), rule2.to_dict()])
            return MitigationResult("CONTAINED_DROP_AND_THROTTLE", applied, fusion=fusion)

        if attack_type == "LOFT_LowRate_Attack":
            rule = self.containment.create_rate_limit_rule(
                dpid=dpid, src_ip=src_ip, max_rate_kbps=500, priority=180, cooldown=cooldown
            )
            applied.append(rule.to_dict())
            return MitigationResult("CONTAINED_RATE_LIMITED", applied, fusion=fusion)

        if attack_type == "RushHour_Burst":
            return MitigationResult(
                "IGNORED_BENIGN_RUSH_HOUR",
                applied,
                false_positive_avoided=False,  # label-only preserve is NOT research FP
                fusion=fusion,
            )

        return MitigationResult("NO_ACTION", applied, fusion=fusion)
