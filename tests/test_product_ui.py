"""Product UI separation: JunctionTrace at / vs research console at /research."""

from __future__ import annotations

from api.app import create_app


def test_root_is_junctiontrace_not_iede():
    app = create_app()
    c = app.test_client()
    r = c.get("/")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "JunctionTrace" in html
    assert "Investigate incident" in html
    assert "A traffic surge is not always an attack" in html
    assert "Tsinghua IEDE" not in html
    assert "IEDE Console" not in html
    assert "Reconstruction error" not in html


def test_research_route_preserves_lab_console():
    app = create_app()
    c = app.test_client()
    r = c.get("/research")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "IEDE" in html or "AI-Assisted SDN-ITS Resilience" in html


def test_capabilities_never_leak_key():
    app = create_app()
    c = app.test_client()
    r = c.get("/api/v1/hackathon/capabilities")
    assert r.status_code == 200
    body = r.get_json()
    assert "nebius_api_key_present" in body
    blob = str(body)
    assert "sk-" not in blob
    assert "NEBIUS_API_KEY" not in blob or body.get("nebius_api_key_present") in {True, False}


def test_conflict_scenario_available():
    app = create_app()
    c = app.test_client()
    r = c.get("/api/v1/hackathon/incidents")
    ids = {s["id"] for s in (r.get_json().get("scenarios") or [])}
    assert "scenario_conflict_signals" in ids
    assert "scenario_rush_vs_attack" in ids
