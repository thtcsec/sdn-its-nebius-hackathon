"""No-crash regression for untrusted telemetry / schema placeholders."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdn_its.camera.fusion import FusionEngine
from sdn_its.llm.agent import run_rule_only
from sdn_its.llm.input_sanitize import safe_float, sanitize_telemetry
from sdn_its.llm.multi_step import run_multi_step_investigation
from sdn_its.llm.schema import (
    RecommendationValidationError,
    normalize_action_name,
    try_validate_recommendation,
    validate_recommendation,
)

ROOT = Path(__file__).resolve().parents[1]
BLIND = ROOT / "datasets" / "hackathon" / "blind"


def test_safe_float_rejects_nan_strings():
    assert safe_float("not_a_number") is None
    assert safe_float("...") is None
    assert safe_float(float("nan")) is None
    assert safe_float("1e9", max_v=100.0) == 100.0
    assert safe_float("-5", min_v=0.0) == 0.0


def test_sanitize_telemetry_marks_unreliable():
    tel, issues = sanitize_telemetry(
        {
            "packet_in_delta_pct": -5,
            "source_dominance": "not_a_number",
            "distributed_sources": "maybe",
            "quality_flag": "unreliable",
        }
    )
    assert tel["_telemetry_unreliable"] is True
    assert "invalid_source_dominance" in issues
    assert tel["source_dominance"] is None


def test_fusion_unreliable_telemetry_observes_no_crash():
    case = json.loads((BLIND / "blind_unreliable_telemetry.json").read_text(encoding="utf-8"))
    dec = FusionEngine().fuse(
        network_prediction=case["network_prediction"],
        physical=case["camera"],
        telemetry=case["telemetry"],
        source_dominance=case["telemetry"].get("source_dominance"),
        distributed_sources=case["telemetry"].get("distributed_sources"),
        packet_in_delta_pct=case["telemetry"].get("packet_in_delta_pct"),
    )
    assert dec.recommended_action == "observe"
    assert "FAIL_CLOSED_UNTRUSTED_TELEMETRY" in dec.reason_codes


def test_rule_only_unreliable_no_crash():
    case = json.loads((BLIND / "blind_unreliable_telemetry.json").read_text(encoding="utf-8"))
    path = run_rule_only(case)
    assert path.ok
    assert path.recommended_action == "observe"


def test_offline_multistep_unreliable_no_crash():
    case = json.loads((BLIND / "blind_unreliable_telemetry.json").read_text(encoding="utf-8"))
    ms = run_multi_step_investigation(case, mode="offline", apply_gate=True, demo_mode=False)
    assert ms.ok
    assert ms.recommendation is not None
    assert ms.recommendation.recommended_action == "observe"
    assert ms.evidence_class == "deterministic_planner"


def test_placeholder_action_rejected():
    with pytest.raises(RecommendationValidationError):
        validate_recommendation(
            {
                "recommended_action": "...",
                "final_risk": "high",
                "rationale": "Placeholder action must never be accepted.",
                "confidence": 0.9,
            }
        )
    assert normalize_action_name("...") is None
    assert normalize_action_name("nuke_switch") is None
    # Safe non-containment alias
    assert normalize_action_name("preserve") == "preserve_rush_hour"
    rec, err = try_validate_recommendation(
        {
            "recommended_action": "preserve",
            "final_risk": "medium",
            "rationale": "Alias maps to preserve_rush_hour only.",
            "confidence": 0.5,
        }
    )
    assert err is None and rec is not None
    assert rec.recommended_action == "preserve_rush_hour"


def test_unknown_verb_not_coerced_to_containment():
    assert normalize_action_name("block") is None
    assert normalize_action_name("drop") is None
    assert normalize_action_name("contain") is None
    rec, err = try_validate_recommendation(
        {
            "recommended_action": "block",
            "final_risk": "high",
            "rationale": "Must fail closed, not become temporary_drop.",
            "confidence": 0.9,
        }
    )
    assert rec is None and err


def test_gate_forces_observe_on_unreliable_telemetry():
    from sdn_its.llm.safety import gate_recommendation

    gated, notes = gate_recommendation(
        {
            "recommended_action": "preserve_rush_hour",
            "final_risk": "medium",
            "rationale": "Model ignored bad telemetry numbers.",
            "confidence": 0.7,
        },
        rule_fusion={"recommended_action": "observe"},
        demo_mode=False,
        allow_containment_in_demo=True,
        evidence_state={"telemetry_unreliable": True, "include_camera": True},
    )
    assert gated.recommended_action == "observe"
    assert any("telemetry_unreliable" in n for n in notes)
