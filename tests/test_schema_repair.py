"""Model output schema acceptance — placeholders must not become containment."""

from __future__ import annotations

from sdn_its.llm.multi_step import _schema_accept
from sdn_its.llm.schema import ALLOWED_ACTIONS


def test_schema_accept_rejects_ellipsis():
    accepted, err = _schema_accept(
        {
            "recommended_action": "...",
            "final_risk": "high",
            "rationale": "Model emitted placeholder ellipsis instead of action.",
            "confidence": 0.8,
            "evidence_notes": ["unit"],
        }
    )
    assert accepted is None
    assert err and "recommended_action" in err


def test_schema_accept_allows_valid_observe():
    accepted, err = _schema_accept(
        {
            "recommended_action": "observe",
            "final_risk": "low",
            "rationale": "Insufficient evidence for any containment action.",
            "confidence": 0.4,
            "evidence_notes": ["unit"],
        }
    )
    assert err is None
    assert accepted is not None
    assert accepted["recommended_action"] == "observe"
    assert accepted["recommended_action"] in ALLOWED_ACTIONS
