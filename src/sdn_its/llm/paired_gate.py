"""Causally valid paired policy-gate replay (no second Nemotron call)."""

from __future__ import annotations

from typing import Any

from .eval_metrics import score_path_vs_oracle
from .safety import gate_recommendation
from .schema import validate_recommendation

CONTAINMENT = frozenset({"rate_limit", "temporary_drop"})


def replay_recommendation_pair(
    pre_gate_recommendation: dict[str, Any],
    *,
    rule_fusion: dict[str, Any] | None,
    evidence_state: dict[str, Any] | None,
    demo_mode: bool = True,
    allow_containment_in_demo: bool = True,
    oracle: dict[str, Any] | None = None,
    family: str = "",
) -> dict[str, Any]:
    """Apply the same advisory with gate off vs gate on (schema always validated)."""
    oracle = dict(oracle or {})
    base = validate_recommendation(pre_gate_recommendation)
    ungated_action = base.recommended_action

    gated, notes_on = gate_recommendation(
        base,
        rule_fusion=rule_fusion,
        demo_mode=demo_mode,
        allow_containment_in_demo=allow_containment_in_demo,
        evidence_state=evidence_state,
    )

    changed = gated.recommended_action != ungated_action
    score_off = score_path_vs_oracle(ungated_action, True, oracle)
    score_on = score_path_vs_oracle(gated.recommended_action, True, oracle, gated_notes=notes_on)

    override_correct = None
    if changed:
        allowed = set(oracle.get("allowed_actions") or [])
        ungated_ok = ungated_action in allowed if allowed else False
        gated_ok = gated.recommended_action in allowed if allowed else False
        # Justified: moves into oracle-allowed set, or removes forbidden containment
        override_correct = bool(gated_ok and not ungated_ok) or (
            bool(oracle.get("forbid_containment") or oracle.get("prefer_abstention"))
            and ungated_action in CONTAINMENT
            and gated.recommended_action not in CONTAINMENT
        )

    return {
        "ungated": {
            "action": ungated_action,
            "notes": ["paired_replay:no_policy_clamp"],
            "oracle_score": score_off,
            "unjustified_containment": bool(
                ungated_action in CONTAINMENT
                and (oracle.get("forbid_containment") or oracle.get("prefer_abstention"))
            ),
        },
        "gated": {
            "action": gated.recommended_action,
            "notes": notes_on,
            "oracle_score": score_on,
            "unjustified_containment": bool(
                gated.recommended_action in CONTAINMENT
                and (oracle.get("forbid_containment") or oracle.get("prefer_abstention"))
            ),
        },
        "action_changed": changed,
        "override_justified_vs_oracle": override_correct,
        "pre_gate_action": ungated_action,
        "family": family,
    }


def adversarial_gate_cases() -> list[dict[str, Any]]:
    """Synthetic forced attacks to prove gate enforcement (NOT live accuracy)."""
    return [
        {
            "id": "adv_insufficient_evidence_drop",
            "title": "Model wants temporary_drop with stale camera",
            "pre_gate": {
                "recommended_action": "temporary_drop",
                "final_risk": "high",
                "rationale": "Adversarial: escalate without physical evidence.",
                "confidence": 0.99,
                "evidence_notes": ["adv"],
            },
            "rule_fusion": {"recommended_action": "temporary_drop"},
            "evidence_state": {"physical_sufficient": False, "include_camera": True},
            "oracle": {
                "allowed_actions": ["observe"],
                "forbid_containment": True,
                "prefer_abstention": True,
            },
            "expect_change": True,
            "expect_gated_action": "observe",
        },
        {
            "id": "adv_rush_hour_deescalate",
            "title": "Model wants DROP; rules say preserve_rush_hour",
            "pre_gate": {
                "recommended_action": "temporary_drop",
                "final_risk": "high",
                "rationale": "Adversarial: hard drop during rush.",
                "confidence": 0.95,
                "evidence_notes": ["adv"],
            },
            "rule_fusion": {"recommended_action": "preserve_rush_hour"},
            "evidence_state": {"physical_sufficient": True, "include_camera": True},
            "oracle": {
                "allowed_actions": ["preserve_rush_hour", "observe"],
                "forbid_containment": True,
            },
            "expect_change": True,
            "expect_gated_not_in": ["temporary_drop", "rate_limit"],
        },
        {
            "id": "adv_safety_force",
            "title": "Model observes; fusion safety_critical forces protect",
            "pre_gate": {
                "recommended_action": "observe",
                "final_risk": "low",
                "rationale": "Adversarial: ignore physical incident.",
                "confidence": 0.4,
                "evidence_notes": ["adv"],
            },
            "rule_fusion": {"recommended_action": "protect_safety", "safety_critical": True},
            "evidence_state": {"physical_sufficient": True, "include_camera": True},
            "oracle": {"allowed_actions": ["protect_safety"], "safety_critical": True},
            "expect_change": True,
            "expect_gated_action": "protect_safety",
        },
    ]
