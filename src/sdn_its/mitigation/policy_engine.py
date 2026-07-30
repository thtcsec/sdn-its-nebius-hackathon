"""Policy engine: map anomaly alerts to Detect -> Contain -> Rollback actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .containment import ContainmentEngine


@dataclass
class MitigationResult:
    mitigation_status: str
    applied_rules: List[Dict[str, Any]] = field(default_factory=list)
    false_positive_avoided: bool = False


class PolicyEngine:
    """Closed-loop mitigation policy matrix for ITS / V2X safety-aware response."""

    def __init__(self, containment: ContainmentEngine):
        self.containment = containment

    def apply(
        self,
        attack_type: str,
        dpid: str,
        src_ip: str = "10.0.0.15",
        dst_ip: Optional[str] = None,
        cooldown: float = 30.0,
    ) -> MitigationResult:
        applied: List[Dict[str, Any]] = []

        if attack_type == "DDoS_PacketIn_Flood":
            rule1 = self.containment.create_drop_rule(
                dpid=dpid, src_ip=src_ip, dst_ip=dst_ip, priority=200, cooldown=cooldown
            )
            rule2 = self.containment.create_packet_in_throttle_rule(
                dpid=dpid, priority=250, cooldown=cooldown
            )
            applied.extend([rule1.to_dict(), rule2.to_dict()])
            return MitigationResult("CONTAINED_DROP_AND_THROTTLE", applied)

        if attack_type == "LOFT_LowRate_Attack":
            rule = self.containment.create_rate_limit_rule(
                dpid=dpid, src_ip=src_ip, max_rate_kbps=500, priority=180, cooldown=cooldown
            )
            applied.append(rule.to_dict())
            return MitigationResult("CONTAINED_RATE_LIMITED", applied)

        if attack_type == "RSU_Link_Fault":
            print(f"[Policy] RSU Link Fault on DPID {dpid}. Triggering path reroute event.")
            return MitigationResult("REROUTED_RSU_FAULT", applied)

        if attack_type == "RushHour_Burst":
            print(
                f"[Policy] Rush-hour burst on DPID {dpid}. "
                "Preserving legitimate V2X flow integrity."
            )
            return MitigationResult("IGNORED_BENIGN_RUSH_HOUR", applied, false_positive_avoided=True)

        return MitigationResult("NO_ACTION", applied)
