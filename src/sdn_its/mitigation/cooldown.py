"""Cooldown tracking helpers for temporary mitigation rules."""

from __future__ import annotations

from typing import Dict, List

from .containment import FlowRule


class CooldownTracker:
    """Tracks which active rules have exceeded their cooldown window."""

    def expired_rule_ids(self, active_rules: Dict[str, FlowRule]) -> List[str]:
        return [rule_id for rule_id, rule in active_rules.items() if rule.is_expired]
