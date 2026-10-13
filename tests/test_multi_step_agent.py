"""Multi-step evidence investigation + ablation (offline, no Nebius spend)."""

from __future__ import annotations

from sdn_its.llm.ablation import run_ablation_arm
from sdn_its.llm.evidence_tools import assess_physical_quality, execute_tool, EvidenceBundle
from sdn_its.llm.multi_step import run_multi_step_investigation
from sdn_its.llm.safety import gate_recommendation
from sdn_its.llm.scenarios import load_all_scenarios, load_scenario


def test_at_least_four_scenarios():
    assert len(load_all_scenarios()) >= 4


def test_physical_quality_missing():
    q = assess_physical_quality(
        {
            "stream_available": False,
            "analytics_valid": False,
            "stale": True,
            "physical_label": "unknown",
        }
    )
    assert q["sufficient"] is False


def test_evidence_gate_blocks_model_containment():
    gated, notes = gate_recommendation(
        {
            "recommended_action": "rate_limit",
            "final_risk": "high",
            "rationale": "Model escalates without physical corroboration.",
            "confidence": 0.9,
        },
        rule_fusion={"recommended_action": "temporary_drop"},
        demo_mode=False,
        allow_containment_in_demo=True,
        evidence_state={"physical_sufficient": False},
    )
    assert gated.recommended_action == "observe"
    assert any("evidence_insufficient" in n for n in notes)


def test_missing_camera_scenario_observes():
    sc = load_scenario("scenario_missing_camera")
    ms = run_multi_step_investigation(
        sc,
        mode="offline",
        include_camera=True,
        apply_gate=True,
        demo_mode=False,
        allow_containment_in_demo=True,
        rule_fusion={"recommended_action": "temporary_drop"},
    )
    assert ms.ok and ms.recommendation is not None
    assert ms.tool_calls >= 3
    assert ms.recommendation.recommended_action == "observe"
    assert ms.evidence_class == "deterministic_planner"
    phases = [t.phase for t in ms.trace]
    assert "detect" in phases and "retrieve_validate" in phases and "policy_gate" in phases


def test_rush_scenario_preserves():
    sc = load_scenario("scenario_rush_vs_attack")
    ms = run_multi_step_investigation(
        sc,
        mode="offline",
        apply_gate=True,
        demo_mode=False,
        allow_containment_in_demo=True,
        rule_fusion={"recommended_action": "preserve_rush_hour"},
    )
    assert ms.ok and ms.recommendation is not None
    assert ms.recommendation.recommended_action in {"preserve_rush_hour", "observe"}
    tools = [t.detail.get("tool") for t in ms.trace if t.phase == "select_evidence_tool"]
    assert "identify_contradictions" in tools


def test_unsafe_synthetic_blocked():
    sc = load_scenario("scenario_unsafe_blocked")
    ms = run_multi_step_investigation(
        sc,
        mode="offline",
        apply_gate=True,
        demo_mode=True,
        allow_containment_in_demo=False,
        rule_fusion={"recommended_action": "preserve_rush_hour"},
    )
    assert ms.ok and ms.recommendation is not None
    assert ms.recommendation.recommended_action not in {"temporary_drop", "rate_limit"}


def test_ablation_arms_offline_same_case():
    sc = load_scenario("scenario_missing_camera")
    # wrap as eval-like
    case = dict(sc)
    a = run_ablation_arm(case, "A_rule_only")
    b = run_ablation_arm(case, "B_net_only", mode="offline", demo_mode=False, allow_containment_in_demo=True)
    c = run_ablation_arm(case, "C_net_cam", mode="offline", demo_mode=False, allow_containment_in_demo=True)
    d = run_ablation_arm(case, "D_net_cam_gate", mode="offline", demo_mode=False, allow_containment_in_demo=True)
    assert a.ok and b.ok and c.ok and d.ok
    assert d.recommended_action == "observe"
    assert (b.fusion or {}).get("include_camera") is False
    assert (d.fusion or {}).get("apply_gate") is True


def test_tool_execution_is_real_not_predetermined_string():
    bundle = EvidenceBundle(
        incident_id="t",
        network_prediction="DDoS_PacketIn_Flood",
        telemetry={"packet_in_delta_pct": 10, "window_id": "w"},
        camera={"stream_available": True, "analytics_valid": True, "stale": False, "physical_label": "stable", "visible_vehicle_tracks": 1, "is_vehicle_count": True},
    )
    r1 = execute_tool("retrieve_network_telemetry", bundle)
    r2 = execute_tool("check_physical_evidence_quality", bundle)
    assert r1.ok and "10" in r1.summary
    assert r2.data.get("sufficient") is True
    assert len(bundle.tool_results) == 2
