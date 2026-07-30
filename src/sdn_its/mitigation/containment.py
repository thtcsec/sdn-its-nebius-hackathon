"""Stage 2 Containment: temporary OpenFlow drop / rate-limit / packet_in throttle rules."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FlowRule:
    """Dataclass representing an active SDN mitigation flow rule."""

    rule_id: str
    dpid: str
    src_ip: str | None
    dst_ip: str | None
    action: str  # "DROP", "RATE_LIMIT", "THROTTLE_PACKET_IN"
    priority: int
    created_at: float
    cooldown_seconds: float
    parameters: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) >= self.cooldown_seconds

    @property
    def remaining_cooldown(self) -> float:
        return max(0.0, self.cooldown_seconds - (time.time() - self.created_at))

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "dpid": self.dpid,
            "src_ip": self.src_ip,
            "dst_ip": self.dst_ip,
            "action": self.action,
            "priority": self.priority,
            "created_at": self.created_at,
            "cooldown_seconds": self.cooldown_seconds,
            "remaining_cooldown_sec": round(self.remaining_cooldown, 1),
            "parameters": self.parameters,
        }


class ContainmentEngine:
    """Creates temporary containment flow rules and pushes them via OpenFlow callback."""

    def __init__(
        self,
        active_rules: dict[str, FlowRule],
        lock,
        of_push_callback: Callable | None = None,
    ):
        self.active_rules = active_rules
        self.lock = lock
        self.of_push_callback = of_push_callback

    def _install(self, rule: FlowRule) -> FlowRule:
        with self.lock:
            self.active_rules[rule.rule_id] = rule
        print(
            f"[Containment] [+] Applied {rule.action} rule {rule.rule_id} "
            f"on DPID {rule.dpid} (cooldown: {rule.cooldown_seconds}s)"
        )
        if self.of_push_callback:
            self.of_push_callback(action="ADD", rule=rule)
        return rule

    def create_drop_rule(
        self,
        dpid: str,
        src_ip: str,
        dst_ip: str | None = None,
        priority: int = 200,
        cooldown: float = 60.0,
    ) -> FlowRule:
        rule = FlowRule(
            rule_id=f"RULE-DROP-{uuid.uuid4().hex[:8]}",
            dpid=dpid,
            src_ip=src_ip,
            dst_ip=dst_ip,
            action="DROP",
            priority=priority,
            created_at=time.time(),
            cooldown_seconds=cooldown,
        )
        return self._install(rule)

    def create_rate_limit_rule(
        self,
        dpid: str,
        src_ip: str,
        max_rate_kbps: int = 500,
        priority: int = 180,
        cooldown: float = 60.0,
    ) -> FlowRule:
        rule = FlowRule(
            rule_id=f"RULE-RATELIMIT-{uuid.uuid4().hex[:8]}",
            dpid=dpid,
            src_ip=src_ip,
            dst_ip=None,
            action="RATE_LIMIT",
            priority=priority,
            created_at=time.time(),
            cooldown_seconds=cooldown,
            parameters={"max_rate_kbps": max_rate_kbps},
        )
        return self._install(rule)

    def create_packet_in_throttle_rule(
        self,
        dpid: str,
        priority: int = 250,
        cooldown: float = 30.0,
    ) -> FlowRule:
        rule = FlowRule(
            rule_id=f"RULE-THROTTLE-{uuid.uuid4().hex[:8]}",
            dpid=dpid,
            src_ip=None,
            dst_ip=None,
            action="THROTTLE_PACKET_IN",
            priority=priority,
            created_at=time.time(),
            cooldown_seconds=cooldown,
        )
        return self._install(rule)
