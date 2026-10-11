"""Telemetry + camera context → Nemotron investigation → gated recommendation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from .nebius_client import (
    DEFAULT_MODEL,
    ChatCompletionResult,
    NebiusAPIError,
    NebiusConfigError,
    NebiusTokenFactoryClient,
)
from .safety import gate_recommendation
from .schema import (
    MitigationRecommendation,
    RecommendationValidationError,
    extract_json_object,
    validate_recommendation,
)

SYSTEM_PROMPT = """You are an SDN-ITS incident investigator for Intelligent Transportation Systems.
You advise a deterministic policy engine. You do NOT execute OpenFlow rules.

Return ONLY a single JSON object with keys:
- recommended_action: one of observe | rate_limit | temporary_drop | preserve_rush_hour | protect_safety
- final_risk: one of low | medium | high | critical
- rationale: short English explanation
- policy_attack_type: string or null (e.g. DDoS_PacketIn_Flood, LOFT_LowRate_Attack, RushHour_Burst, Normal)
- cooldown_seconds: number between 5 and 60
- false_positive_corrected: boolean
- safety_critical: boolean
- confidence: number between 0 and 1
- evidence_notes: array of short strings

Rules:
- Network anomaly evidence is primary; camera is same-zone physical context only.
- If pedestrians/incident/safety_critical, prefer protect_safety.
- If rush-hour physical activity explains a surge, prefer preserve_rush_hour or observe.
- Prefer observe when uncertain.
- Never invent packet counters that are not in the context.
"""


@dataclass
class IncidentContext:
    network_prediction: str
    telemetry: dict[str, Any] = field(default_factory=dict)
    camera: dict[str, Any] = field(default_factory=dict)
    rule_fusion: dict[str, Any] | None = None
    dpid: str = "1"
    src_ip: str = "10.0.0.15"

    def to_prompt_payload(self) -> dict[str, Any]:
        return {
            "network_prediction": self.network_prediction,
            "telemetry": self.telemetry,
            "camera_physical_context": self.camera,
            "rule_based_fusion": self.rule_fusion,
            "dpid": self.dpid,
            "src_ip": self.src_ip,
        }


@dataclass
class InvestigationResult:
    ok: bool
    evidence_class: str  # real_api | mocked_transport | blocked_no_credentials | validation_error | api_error
    recommendation: MitigationRecommendation | None
    gated_notes: list[str] = field(default_factory=list)
    fusion_for_policy: dict[str, Any] | None = None
    model: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: float | None = None
    estimated_cost_usd: float | None = None
    completion_id: str | None = None
    error: str | None = None
    raw_content_preview: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.recommendation is not None:
            d["recommendation"] = self.recommendation.to_dict()
        return d


def build_user_prompt(ctx: IncidentContext) -> str:
    return (
        "Investigate this SDN-ITS incident context and return the JSON recommendation.\n"
        + json.dumps(ctx.to_prompt_payload(), indent=2, default=str)
    )


def investigate_incident(
    ctx: IncidentContext,
    *,
    client: NebiusTokenFactoryClient | None = None,
    demo_mode: bool = True,
    allow_containment_in_demo: bool = False,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 512,
) -> InvestigationResult:
    """Run a real Token Factory completion when credentials exist; never fabricate success."""
    try:
        tf = client or NebiusTokenFactoryClient(model=model or DEFAULT_MODEL)
        # Force key check early for clear evidence_class
        from .nebius_client import load_api_key

        load_api_key(tf.api_key)
    except NebiusConfigError as exc:
        return InvestigationResult(
            ok=False,
            evidence_class="blocked_no_credentials",
            recommendation=None,
            error=str(exc),
        )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(ctx)},
    ]

    try:
        completion = tf.chat_completions(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
    except NebiusAPIError as exc:
        # Retry once without response_format if server rejects it
        if exc.status_code in {400, 422} and "response_format" in str(exc.body).lower():
            try:
                completion = tf.chat_completions(
                    messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=None,
                )
            except NebiusAPIError as exc2:
                return InvestigationResult(
                    ok=False,
                    evidence_class="api_error",
                    recommendation=None,
                    error=str(exc2),
                    model=model or DEFAULT_MODEL,
                )
        else:
            return InvestigationResult(
                ok=False,
                evidence_class="api_error",
                recommendation=None,
                error=str(exc),
                model=model or DEFAULT_MODEL,
            )
    except NebiusConfigError as exc:
        return InvestigationResult(
            ok=False,
            evidence_class="blocked_no_credentials",
            recommendation=None,
            error=str(exc),
        )

    return _finalize_from_completion(
        completion,
        rule_fusion=ctx.rule_fusion,
        demo_mode=demo_mode,
        allow_containment_in_demo=allow_containment_in_demo,
    )


def investigate_from_model_text(
    content: str,
    *,
    rule_fusion: dict[str, Any] | None = None,
    demo_mode: bool = True,
    allow_containment_in_demo: bool = False,
    evidence_class: str = "mocked_transport",
    model: str | None = None,
    usage: dict[str, int] | None = None,
    latency_ms: float | None = None,
) -> InvestigationResult:
    """Parse/validate/gate a model string — used by unit tests (mocked_transport evidence)."""
    fake = ChatCompletionResult(
        content=content,
        model=model or "mock-model",
        finish_reason="stop",
        usage=usage or {},
        latency_ms=latency_ms or 0.0,
        evidence_class=evidence_class,
    )
    return _finalize_from_completion(
        fake,
        rule_fusion=rule_fusion,
        demo_mode=demo_mode,
        allow_containment_in_demo=allow_containment_in_demo,
        evidence_class_override=evidence_class,
    )


def _finalize_from_completion(
    completion: ChatCompletionResult,
    *,
    rule_fusion: dict[str, Any] | None,
    demo_mode: bool,
    allow_containment_in_demo: bool,
    evidence_class_override: str | None = None,
) -> InvestigationResult:
    preview = (completion.content or "")[:240]
    try:
        obj = extract_json_object(completion.content)
        rec = validate_recommendation(obj)
        gated, notes = gate_recommendation(
            rec,
            rule_fusion=rule_fusion,
            demo_mode=demo_mode,
            allow_containment_in_demo=allow_containment_in_demo,
        )
    except RecommendationValidationError as exc:
        return InvestigationResult(
            ok=False,
            evidence_class="validation_error",
            recommendation=None,
            error=str(exc),
            model=completion.model,
            usage=completion.usage,
            latency_ms=completion.latency_ms,
            estimated_cost_usd=completion.estimated_cost_usd()
            if completion.evidence_class == "real_api"
            else None,
            completion_id=completion.raw_id,
            raw_content_preview=preview,
        )

    evidence = evidence_class_override or completion.evidence_class
    cost = completion.estimated_cost_usd() if evidence == "real_api" else None
    return InvestigationResult(
        ok=True,
        evidence_class=evidence,
        recommendation=gated,
        gated_notes=notes,
        fusion_for_policy=gated.to_fusion_dict(),
        model=completion.model,
        usage=completion.usage,
        latency_ms=completion.latency_ms,
        estimated_cost_usd=cost,
        completion_id=completion.raw_id,
        raw_content_preview=preview,
    )
