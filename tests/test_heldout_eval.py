"""Held-out eval set integrity + oracle scoring (no Nebius required)."""

from __future__ import annotations

from sdn_its.llm.eval_metrics import score_path_vs_oracle
from sdn_its.llm.eval_set import assert_disjoint_from_dev, load_eval_cases


def test_heldout_exists_and_disjoint():
    cases = load_eval_cases()
    assert len(cases) >= 20
    assert_disjoint_from_dev(cases)
    assert all(c.get("split") == "heldout_eval" for c in cases)
    assert all("oracle" in c for c in cases)


def test_no_dev_fixture_ids_in_eval():
    from sdn_its.llm.fixtures import load_all_incidents

    dev = {i["id"] for i in load_all_incidents()}
    ev = {c["id"] for c in load_eval_cases()}
    assert not (dev & ev)


def test_oracle_scoring_false_escalation():
    oracle = {"allowed_actions": ["observe"], "forbid_containment": True, "safety_critical": False}
    s = score_path_vs_oracle("temporary_drop", True, oracle)
    assert s["false_escalation"] is True
    assert s["correct_vs_oracle"] is False


def test_incidents_readme_marks_regression_only():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "datasets/hackathon/incidents/README.md").read_text(
        encoding="utf-8"
    )
    assert "NOT accuracy" in text or "regression" in text.lower()
