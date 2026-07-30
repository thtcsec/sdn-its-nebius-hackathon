"""Cooldown tracking helpers for temporary mitigation rules."""

from __future__ import annotations

from .containment import FlowRule


class CooldownTracker:
    """Tracks which active rules have exceeded their cooldown window."""

    def expired_rule_ids(self, active_rules: dict[str, FlowRule]) -> list[str]:
        return [rule_id for rule_id, rule in active_rules.items() if rule.is_expired]
