"""Stage 3 Rollback: revoke temporary flow rules and record history."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from .containment import FlowRule
from .cooldown import CooldownTracker


class RollbackManager:
    """Revokes expired or manual rules and keeps rollback history."""

    def __init__(
        self,
        active_rules: dict[str, FlowRule],
        lock: threading.Lock,
        of_push_callback: Callable | None = None,
        check_interval: float = 5.0,
    ):
        self.active_rules = active_rules
        self.lock = lock
        self.of_push_callback = of_push_callback
        self.check_interval = check_interval
        self.rollback_history: list[dict[str, Any]] = []
        self.cooldown = CooldownTracker()
        self.running = True
        self._thread = threading.Thread(target=self._auto_rollback_loop, daemon=True)
        self._thread.start()

    def revoke_rule(self, rule_id: str, reason: str = "MANUAL_REVOCATION") -> bool:
        with self.lock:
            if rule_id not in self.active_rules:
                return False
            rule = self.active_rules.pop(rule_id)

        print(
            f"[Rollback] [-] Revoked rule {rule_id} ({rule.action}) "
            f"on DPID {rule.dpid}. Reason: {reason}"
        )
        history_entry = rule.to_dict()
        history_entry["revoked_at"] = time.time()
        history_entry["revocation_reason"] = reason
        self.rollback_history.append(history_entry)

        if self.of_push_callback:
            self.of_push_callback(action="DELETE", rule=rule)
        return True

    def _auto_rollback_loop(self):
        while self.running:
            time.sleep(self.check_interval)
            with self.lock:
                expired_ids = self.cooldown.expired_rule_ids(self.active_rules)
            for rid in expired_ids:
                self.revoke_rule(rid, reason="COOLDOWN_EXPIRED")

    def stop(self):
        self.running = False
