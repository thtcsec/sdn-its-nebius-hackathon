"""Hackathon cyber-physical agent + benchmark fixtures (offline, no Nebius required)."""

from __future__ import annotations

from sdn_its.llm.agent import investigate_case
from sdn_its.llm.audit_log import clear_audit, list_audit
from sdn_its.llm.fixtures import load_all_incidents, load_incident


def test_at_least_four_fixtures():
    assert len(load_all_incidents()) >= 4


def test_unsafe_escalation_blocked():
    clear_audit()
    inc = load_incident("07_unsafe_escalation_blocked")
    case = investigate_case(inc, mode="offline", demo_mode=True)
    assert case.nemotron.recommended_action not in {"temporary_drop", "rate_limit"}
    assert case.metrics.get("gate_block_as_expected") is True
    assert any("gate:" in n for n in case.nemotron.gated_notes) or case.nemotron.recommended_action == "protect_safety"


def test_malformed_fail_closed():
    inc = load_incident("05_malformed_model_output")
    case = investigate_case(inc, mode="offline", demo_mode=True)
    assert case.nemotron.ok is False
    assert case.rule.ok is True
    assert case.metrics.get("validation_failed_as_expected") is True


def test_unavailable_api_fail_closed(monkeypatch):
    # force_mode handles empty key internally; still ensure process can have a key
    inc = load_incident("06_unavailable_nebius_api")
    case = investigate_case(inc, mode="offline", demo_mode=True)
    assert case.nemotron.evidence_class == "blocked_no_credentials"
    assert case.rule.ok is True
    assert case.metrics.get("api_unavailable_as_expected") is True


def test_rush_hour_no_inappropriate_containment():
    inc = load_incident("01_legitimate_rush_hour")
    case = investigate_case(
        inc, mode="offline", demo_mode=True, allow_containment_in_demo=True
    )
    assert case.metrics.get("inappropriate_containment") is False
    assert case.rule.recommended_action in {"preserve_rush_hour", "observe", "protect_safety"}


def test_api_hackathon_routes():
    from api.app import create_app

    clear_audit()
    app = create_app()
    c = app.test_client()
    r = c.get("/api/v1/hackathon/incidents")
    assert r.status_code == 200
    body0 = r.get_json()
    assert len(body0["incidents"]) >= 4
    assert len(body0.get("scenarios") or []) >= 4
    r2 = c.post(
        "/api/v1/hackathon/run",
        json={"incident_id": "07_unsafe_escalation_blocked", "mode": "offline", "demo_mode": True},
    )
    assert r2.status_code == 200
    body = r2.get_json()
    assert body["nemotron"]["recommended_action"] != "temporary_drop"
    r_ms = c.post(
        "/api/v1/hackathon/multistep",
        json={"scenario_id": "scenario_missing_camera", "mode": "offline", "demo_mode": True, "apply_gate": True},
    )
    assert r_ms.status_code == 200
    ms = r_ms.get_json()
    assert ms.get("tool_calls", 0) >= 3
    assert (ms.get("recommendation") or {}).get("recommended_action") == "observe"
    assert ms.get("trace")
    r3 = c.get("/api/v1/hackathon/audit")
    assert r3.status_code == 200
    assert list_audit()


def test_offline_benchmark_script(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    out = tmp_path / "bench.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "run_hackathon_benchmark.py"),
            "--mode",
            "offline",
            "--allow-containment-in-demo",
            "--out",
            str(out),
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert out.is_file()
