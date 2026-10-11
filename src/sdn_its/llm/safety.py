"""Deterministic safety gates between LLM advice and PolicyEngine."""

from __future__ import annotations

from typing import Any

from .schema import ALLOWED_ACTIONS, MitigationRecommendation, validate_recommendation

# Actions that install containment rules (still mock OF by default in demo)
CONTAINMENT_ACTIONS = frozenset({"rate_limit", "temporary_drop"})

# Rank for de-escalation only (higher = more aggressive)
_ACTION_RANK = {
    "observe": 0,
    "protect_safety": 0,
    "preserve_rush_hour": 1,
    "rate_limit": 2,
    "temporary_drop": 3,
}


def gate_recommendation(
    candidate: MitigationRecommendation | dict[str, Any],
    *,
    rule_fusion: dict[str, Any] | None = None,
    demo_mode: bool = True,
    allow_containment_in_demo: bool = False,
) -> tuple[MitigationRecommendation, list[str]]:
    """Clamp LLM advice so deterministic policy remains authoritative.

    Rules:
    - Always re-validate schema.
    - Safety-critical physical context forces protect_safety.
    - LLM may not escalate beyond rule-based fusion action when fusion is present.
    - In demo_mode, containment actions are downgraded to observe unless explicitly allowed
      (OpenFlow remains mock by default; this prevents intending destructive policy states).
    """
    notes: list[str] = []
    rec = validate_recommendation(candidate)
    fusion = rule_fusion or {}

    if bool(fusion.get("safety_critical")) or bool(fusion.get("physical_label") == "incident"):
        if rec.recommended_action != "protect_safety":
            notes.append("gate:forced_protect_safety")
            rec.recommended_action = "protect_safety"
            rec.safety_critical = True
            rec.final_risk = "critical"

    rule_action = fusion.get("recommended_action")
    if rule_action in ALLOWED_ACTIONS:
        if _ACTION_RANK.get(rec.recommended_action, 0) > _ACTION_RANK.get(str(rule_action), 0):
            notes.append(f"gate:deescalated_to_rule:{rule_action}")
            rec.recommended_action = str(rule_action)
            if fusion.get("policy_attack_type"):
                rec.policy_attack_type = fusion.get("policy_attack_type")
            if fusion.get("cooldown_seconds") is not None:
                rec.cooldown_seconds = float(fusion["cooldown_seconds"])

    if demo_mode and rec.recommended_action in CONTAINMENT_ACTIONS and not allow_containment_in_demo:
        notes.append("gate:demo_block_containment")
        rec.recommended_action = "observe"
        rec.rationale = (
            rec.rationale + " [demo_mode: containment intention blocked; OF remains non-destructive]"
        ).strip()

    # Re-validate after mutations
    rec = validate_recommendation(rec.to_dict())
    return rec, notes
