"""Flow rule manager composing Containment + Rollback (compat with prior FlowRuleManager API)."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from sdn_its.mitigation.containment import ContainmentEngine, FlowRule
from sdn_its.mitigation.rollback import RollbackManager


class FlowRuleManager:
    """Manages active SDN flow rules, switch modifications, and automated rollback."""

    def __init__(
        self,
        rollback_check_interval: float = 5.0,
        of_push_callback: Callable | None = None,
    ):
        self.active_rules: dict[str, FlowRule] = {}
        self.lock = threading.Lock()
        self.of_push_callback = of_push_callback
        self.containment = ContainmentEngine(
            active_rules=self.active_rules,
            lock=self.lock,
            of_push_callback=of_push_callback,
        )
        self.rollback = RollbackManager(
            active_rules=self.active_rules,
            lock=self.lock,
            of_push_callback=of_push_callback,
            check_interval=rollback_check_interval,
        )

    @property
    def rollback_history(self) -> list[dict[str, Any]]:
        return self.rollback.rollback_history

    def create_drop_rule(self, *args, **kwargs) -> FlowRule:
        return self.containment.create_drop_rule(*args, **kwargs)

    def create_rate_limit_rule(self, *args, **kwargs) -> FlowRule:
        return self.containment.create_rate_limit_rule(*args, **kwargs)

    def create_packet_in_throttle_rule(self, *args, **kwargs) -> FlowRule:
        return self.containment.create_packet_in_throttle_rule(*args, **kwargs)

    def revoke_rule(self, rule_id: str, reason: str = "MANUAL_REVOCATION") -> bool:
        return self.rollback.revoke_rule(rule_id, reason=reason)

    def get_all_active_rules(self) -> list[dict[str, Any]]:
        with self.lock:
            return [rule.to_dict() for rule in self.active_rules.values()]

    def stop(self):
        self.rollback.stop()
