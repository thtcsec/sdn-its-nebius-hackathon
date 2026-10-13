"""Paired gate replay causality + adversarial enforcement (no Nebius)."""

from __future__ import annotations

from sdn_its.llm.paired_gate import adversarial_gate_cases, replay_recommendation_pair


def test_paired_replay_no_change_when_already_safe():
    pair = replay_recommendation_pair(
        {
            "recommended_action": "observe",
            "final_risk": "medium",
            "rationale": "Already abstaining under uncertainty.",
            "confidence": 0.5,
        },
        rule_fusion={"recommended_action": "observe"},
        evidence_state={"physical_sufficient": False},
        demo_mode=False,
        allow_containment_in_demo=True,
        oracle={"allowed_actions": ["observe"], "prefer_abstention": True},
    )
    assert pair["ungated"]["action"] == "observe"
    assert pair["gated"]["action"] == "observe"
    assert pair["action_changed"] is False


def test_adversarial_cases_enforce_gate():
    for adv in adversarial_gate_cases():
        pair = replay_recommendation_pair(
            adv["pre_gate"],
            rule_fusion=adv.get("rule_fusion"),
            evidence_state=adv.get("evidence_state"),
            demo_mode=False,
            allow_containment_in_demo=True,
            oracle=adv.get("oracle"),
        )
        if adv.get("expect_change"):
            assert pair["action_changed"] is True, adv["id"]
        if adv.get("expect_gated_action"):
            assert pair["gated"]["action"] == adv["expect_gated_action"], adv["id"]
        if adv.get("expect_gated_not_in"):
            assert pair["gated"]["action"] not in set(adv["expect_gated_not_in"]), adv["id"]
