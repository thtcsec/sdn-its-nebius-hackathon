"""Structured mitigation recommendation schema + validation (no network I/O)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

ALLOWED_ACTIONS = frozenset(
    {
        "observe",
        "rate_limit",
        "temporary_drop",
        "preserve_rush_hour",
        "protect_safety",
    }
)

ALLOWED_RISK = frozenset({"low", "medium", "high", "critical"})

# Cooldown bounds enforced before policy sees the recommendation
COOLDOWN_MIN_S = 5.0
COOLDOWN_MAX_S = 60.0


class RecommendationValidationError(ValueError):
    """Raised when model output cannot be accepted as a mitigation recommendation."""


@dataclass
class MitigationRecommendation:
    """Validated advisory recommendation for PolicyEngine fusion fields."""

    recommended_action: str
    final_risk: str
    rationale: str
    policy_attack_type: str | None = None
    cooldown_seconds: float | None = 30.0
    false_positive_corrected: bool = False
    safety_critical: bool = False
    confidence: float = 0.0
    evidence_notes: list[str] = field(default_factory=list)
    schema_version: str = "hackathon_mitigation_v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_fusion_dict(self) -> dict[str, Any]:
        """Shape accepted by baseline PolicyEngine.apply(fusion=...)."""
        return {
            "recommended_action": self.recommended_action,
            "policy_attack_type": self.policy_attack_type,
            "cooldown_seconds": self.cooldown_seconds,
            "false_positive_corrected": self.false_positive_corrected,
            "safety_critical": self.safety_critical,
            "final_risk": self.final_risk,
            "explain": self.rationale,
            "reason_codes": list(self.evidence_notes),
            "llm_schema_version": self.schema_version,
            "llm_confidence": self.confidence,
        }


_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def _balanced_json_objects(text: str) -> list[str]:
    """Return candidate JSON object substrings (brace-balanced), last-first preferred later."""
    out: list[str] = []
    depth = 0
    start: int | None = None
    in_str = False
    escape = False
    for i, ch in enumerate(text):
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                out.append(text[start : i + 1])
                start = None
    return out


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from model text (raw, fenced, or trailing after reasoning)."""
    if not text or not str(text).strip():
        raise RecommendationValidationError("empty model content")
    raw = str(text).strip()
    candidates: list[str] = []
    m = _JSON_FENCE.search(raw)
    if m:
        candidates.append(m.group(1))
    # Prefer the last balanced object (common for reasoning models that narrate then emit JSON)
    balanced = _balanced_json_objects(raw)
    candidates.extend(reversed(balanced))
    candidates.append(raw)

    last_err: Exception | None = None
    for cand in candidates:
        try:
            obj = json.loads(cand)
        except json.JSONDecodeError as exc:
            last_err = exc
            continue
        if isinstance(obj, dict):
            return obj
        last_err = RecommendationValidationError("JSON root must be an object")
    raise RecommendationValidationError(f"could not parse JSON object: {last_err}")


def validate_recommendation(payload: dict[str, Any] | MitigationRecommendation) -> MitigationRecommendation:
    """Validate and normalize a recommendation dict."""
    if isinstance(payload, MitigationRecommendation):
        data = payload.to_dict()
    elif isinstance(payload, dict):
        data = dict(payload)
    else:
        raise RecommendationValidationError("recommendation must be a dict")

    action = str(data.get("recommended_action") or "").strip()
    if action not in ALLOWED_ACTIONS:
        raise RecommendationValidationError(
            f"recommended_action must be one of {sorted(ALLOWED_ACTIONS)}; got {action!r}"
        )

    risk = str(data.get("final_risk") or "").strip().lower()
    if risk not in ALLOWED_RISK:
        raise RecommendationValidationError(
            f"final_risk must be one of {sorted(ALLOWED_RISK)}; got {risk!r}"
        )

    rationale = str(data.get("rationale") or data.get("explain") or "").strip()
    if len(rationale) < 8:
        raise RecommendationValidationError("rationale must be a non-trivial string")

    cooldown_raw = data.get("cooldown_seconds", 30.0)
    if cooldown_raw is None:
        cooldown: float | None = None
    else:
        try:
            cooldown = float(cooldown_raw)
        except (TypeError, ValueError) as exc:
            raise RecommendationValidationError("cooldown_seconds must be a number") from exc
        if cooldown < COOLDOWN_MIN_S or cooldown > COOLDOWN_MAX_S:
            cooldown = min(COOLDOWN_MAX_S, max(COOLDOWN_MIN_S, cooldown))

    conf_raw = data.get("confidence", 0.0)
    try:
        confidence = float(conf_raw)
    except (TypeError, ValueError) as exc:
        raise RecommendationValidationError("confidence must be a number") from exc
    confidence = min(1.0, max(0.0, confidence))

    notes = data.get("evidence_notes") or data.get("reason_codes") or []
    if not isinstance(notes, list):
        raise RecommendationValidationError("evidence_notes must be a list")
    evidence_notes = [str(x) for x in notes][:12]

    pat = data.get("policy_attack_type")
    policy_attack_type = None if pat in (None, "") else str(pat)

    return MitigationRecommendation(
        recommended_action=action,
        final_risk=risk,
        rationale=rationale,
        policy_attack_type=policy_attack_type,
        cooldown_seconds=cooldown,
        false_positive_corrected=bool(data.get("false_positive_corrected", False)),
        safety_critical=bool(data.get("safety_critical", False)),
        confidence=confidence,
        evidence_notes=evidence_notes,
        schema_version=str(data.get("schema_version") or "hackathon_mitigation_v1"),
    )
