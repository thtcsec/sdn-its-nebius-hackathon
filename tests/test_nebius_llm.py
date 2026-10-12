"""Hackathon Nebius/Nemotron vertical-slice tests.

Evidence labeling:
  - Unit tests use mocked_transport / pure functions — NOT real Nebius calls.
  - Real API coverage is scripts/verify_nebius_nemotron.py when NEBIUS_API_KEY is set.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from sdn_its.llm.investigation import (
    IncidentContext,
    investigate_from_model_text,
    investigate_incident,
)
from sdn_its.llm.nebius_client import NebiusAPIError, NebiusConfigError, NebiusTokenFactoryClient
from sdn_its.llm.safety import gate_recommendation
from sdn_its.llm.schema import RecommendationValidationError, validate_recommendation
from sdn_its.controller.flow_manager import FlowRuleManager
from sdn_its.mitigation.policy_engine import PolicyEngine


def test_extract_json_after_reasoning_preamble():
    from sdn_its.llm.schema import extract_json_object

    text = (
        "Here's a thinking process:\n1. analyze\n"
        '{"recommended_action":"observe","final_risk":"low",'
        '"rationale":"Uncertain evidence warrants observe only.",'
        '"confidence":0.5,"evidence_notes":["unit"]}'
    )
    obj = extract_json_object(text)
    assert obj["recommended_action"] == "observe"


def test_validate_recommendation_ok():
    rec = validate_recommendation(
        {
            "recommended_action": "observe",
            "final_risk": "low",
            "rationale": "Insufficient evidence for containment.",
            "confidence": 0.7,
            "evidence_notes": ["stable_camera"],
        }
    )
    assert rec.recommended_action == "observe"
    fusion = rec.to_fusion_dict()
    assert fusion["recommended_action"] == "observe"


def test_validate_recommendation_rejects_bad_action():
    with pytest.raises(RecommendationValidationError):
        validate_recommendation(
            {
                "recommended_action": "nuke_switch",
                "final_risk": "high",
                "rationale": "bad action should fail validation path",
            }
        )


def test_gate_deescalates_and_demo_blocks_containment():
    rule = {"recommended_action": "observe", "safety_critical": False}
    gated, notes = gate_recommendation(
        {
            "recommended_action": "temporary_drop",
            "final_risk": "high",
            "rationale": "Model tried to escalate beyond rule fusion.",
            "confidence": 0.9,
        },
        rule_fusion=rule,
        demo_mode=True,
        allow_containment_in_demo=False,
    )
    assert gated.recommended_action == "observe"
    assert any("deescalated" in n or "demo_block" in n for n in notes)


def test_gate_forces_protect_safety():
    gated, notes = gate_recommendation(
        {
            "recommended_action": "temporary_drop",
            "final_risk": "high",
            "rationale": "Should yield to safety-critical physical context.",
        },
        rule_fusion={"safety_critical": True, "recommended_action": "protect_safety"},
        demo_mode=True,
    )
    assert gated.recommended_action == "protect_safety"
    assert "gate:forced_protect_safety" in notes or gated.safety_critical


def test_investigate_from_model_text_feeds_policy_engine():
    content = json.dumps(
        {
            "recommended_action": "rate_limit",
            "final_risk": "medium",
            "rationale": "Low-rate anomaly with stable camera context.",
            "policy_attack_type": "LOFT_LowRate_Attack",
            "cooldown_seconds": 15,
            "confidence": 0.8,
            "evidence_notes": ["unit_test_mocked_transport"],
        }
    )
    result = investigate_from_model_text(
        content,
        rule_fusion={"recommended_action": "rate_limit", "policy_attack_type": "LOFT_LowRate_Attack"},
        demo_mode=False,  # allow containment intention for policy mapping test
        evidence_class="mocked_transport",
    )
    assert result.ok
    assert result.evidence_class == "mocked_transport"
    assert result.fusion_for_policy is not None
    mgr = FlowRuleManager(of_push_callback=None)
    mit = PolicyEngine(mgr.containment).apply(
        "LOFT_LowRate_Attack",
        dpid="1",
        src_ip="10.0.0.15",
        fusion=result.fusion_for_policy,
    )
    assert mit.mitigation_status == "CONTAINED_RATE_LIMITED"
    assert mit.applied_rules  # in-memory rules only — not switch evidence


def test_investigate_incident_blocked_without_credentials(monkeypatch):
    # Empty process env wins over repo .env (override=False)
    monkeypatch.setenv("NEBIUS_API_KEY", "")
    ctx = IncidentContext(network_prediction="Normal", telemetry={"x": 1}, camera={"y": 2})
    result = investigate_incident(ctx)
    assert result.ok is False
    assert result.evidence_class == "blocked_no_credentials"


def test_nebius_client_chat_mocked_http():
    """HTTP transport mocked — evidence is mocked_transport, not real_api."""
    session = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "id": "chatcmpl-test",
        "model": "nvidia/Nemotron-3_5-Lightning",
        "choices": [{"finish_reason": "stop", "message": {"content": '{"ping":true}'}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    session.post.return_value = resp

    client = NebiusTokenFactoryClient(api_key="test-key-not-real", session=session)
    out = client.chat_completions([{"role": "user", "content": "hi"}], max_tokens=16)
    assert out.content == '{"ping":true}'
    assert out.usage["total_tokens"] == 15
    assert out.evidence_class == "mocked_transport"
    session.post.assert_called_once()


def test_nebius_client_http_error():
    session = MagicMock()
    resp = MagicMock()
    resp.status_code = 401
    resp.json.return_value = {"error": {"message": "unauthorized"}}
    resp.text = '{"error":{"message":"unauthorized"}}'
    session.post.return_value = resp
    client = NebiusTokenFactoryClient(api_key="bad", session=session)
    with pytest.raises(NebiusAPIError) as ei:
        client.chat_completions([{"role": "user", "content": "hi"}])
    assert ei.value.status_code == 401


def test_load_api_key_missing(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "")
    with pytest.raises(NebiusConfigError):
        NebiusTokenFactoryClient(api_key=None).list_models()


def test_repo_env_loads_from_project_root_not_cwd(monkeypatch, tmp_path):
    """``.env`` is resolved via PROJECT_ROOT even when cwd differs."""
    from sdn_its.utils.env import env_file_path, load_repo_env, nebius_config_summary
    from sdn_its.utils.paths import PROJECT_ROOT

    monkeypatch.chdir(tmp_path)
    path = env_file_path()
    assert path == PROJECT_ROOT / ".env"
    assert path.is_absolute()
    # Loading must not depend on cwd
    loaded = load_repo_env(override=False)
    summary = nebius_config_summary()
    assert summary["project_root"] == str(PROJECT_ROOT)
    assert summary["cwd"] == str(tmp_path)
    assert "NEBIUS_API_KEY" not in json.dumps(summary)
    if (PROJECT_ROOT / ".env").is_file():
        assert loaded == PROJECT_ROOT / ".env"
        assert summary["env_file_exists"] is True


def test_classify_http_error_auth():
    from sdn_its.llm.nebius_client import ERROR_AUTH, classify_http_error

    assert classify_http_error(401, {"error": {"message": "unauthorized"}}) == ERROR_AUTH
