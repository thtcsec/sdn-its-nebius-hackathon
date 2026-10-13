"""Telemetry + camera context → Nemotron investigation → gated recommendation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from sdn_its.utils.env import ensure_repo_env

from .nebius_client import (
    DEFAULT_MODEL,
    FALLBACK_INVESTIGATION_MODEL,
    ChatCompletionResult,
    NebiusAPIError,
    NebiusConfigError,
    NebiusTokenFactoryClient,
)
from .evidence_tools import assess_physical_quality
from .safety import gate_recommendation
from .schema import (
    MitigationRecommendation,
    RecommendationValidationError,
    extract_json_object,
    validate_recommendation,
)

SYSTEM_PROMPT = """You are an SDN-ITS incident investigator for Intelligent Transportation Systems.
You advise a deterministic policy engine. You do NOT execute OpenFlow rules.

CRITICAL OUTPUT RULES:
- Your entire reply MUST be one JSON object and nothing else.
- Do not write analysis, markdown, code fences, or chain-of-thought before/after the JSON.
- Start with `{` and end with `}`.

Required JSON keys:
- recommended_action: one of observe | rate_limit | temporary_drop | preserve_rush_hour | protect_safety
- final_risk: one of low | medium | high | critical
- rationale: short English explanation
- policy_attack_type: string or null (e.g. DDoS_PacketIn_Flood, LOFT_LowRate_Attack, RushHour_Burst, Normal)
- cooldown_seconds: number between 5 and 60
- false_positive_corrected: boolean
- safety_critical: boolean
- confidence: number between 0 and 1
- evidence_notes: array of short strings

Policy guidance:
- A network traffic surge is not always an attack — weigh same-zone physical context.
- Camera fields are physical-context metadata (may be synthetic); never claim live RTSP inference.
- If camera stream/analytics are missing, stale, or invalid, prefer observe — do not escalate containment.
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
    error_class: str | None = None
    raw_content_preview: str | None = None
    http_status: int | None = None

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
    temperature: float = 0.1,
    max_tokens: int = 1024,
) -> InvestigationResult:
    """Run a real Token Factory completion when credentials exist; never fabricate success."""
    ensure_repo_env()
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
            error_class=getattr(exc, "error_class", "config"),
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
        if exc.status_code in {400, 422}:
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
                    error_class=exc2.error_class,
                    http_status=exc2.status_code,
                    model=model or DEFAULT_MODEL,
                )
        else:
            return InvestigationResult(
                ok=False,
                evidence_class="api_error",
                recommendation=None,
                error=str(exc),
                error_class=exc.error_class,
                http_status=exc.status_code,
                model=model or DEFAULT_MODEL,
            )

    evidence_state = {
        "physical_sufficient": assess_physical_quality(ctx.camera).get("sufficient"),
        "include_camera": True,
    }
    # If the model spent the budget on reasoning and never emitted JSON, one repair call
    finalized = _finalize_from_completion(
        completion,
        rule_fusion=ctx.rule_fusion,
        demo_mode=demo_mode,
        allow_containment_in_demo=allow_containment_in_demo,
        evidence_state=evidence_state,
    )
    if finalized.ok or finalized.evidence_class != "validation_error":
        return finalized

    repair_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(ctx)},
        {"role": "assistant", "content": completion.content},
        {
            "role": "user",
            "content": (
                "Your previous reply was invalid. Reply again with ONLY the JSON object "
                "(no thinking, no prose). It must parse with json.loads."
            ),
        },
    ]
    try:
        completion = tf.chat_completions(
            repair_messages,
            model=model,
            temperature=0.0,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
    except NebiusAPIError as exc:
        return InvestigationResult(
            ok=False,
            evidence_class="api_error",
            recommendation=None,
            error=str(exc),
            error_class=exc.error_class,
            http_status=exc.status_code,
            model=model or DEFAULT_MODEL,
            raw_content_preview=(finalized.raw_content_preview),
        )
    except NebiusConfigError as exc:
        return InvestigationResult(
            ok=False,
            evidence_class="blocked_no_credentials",
            recommendation=None,
            error=str(exc),
            error_class=getattr(exc, "error_class", "config"),
        )

    repaired = _finalize_from_completion(
        completion,
        rule_fusion=ctx.rule_fusion,
        demo_mode=demo_mode,
        allow_containment_in_demo=allow_containment_in_demo,
        evidence_state=evidence_state,
    )
    if repaired.ok or repaired.evidence_class != "validation_error":
        return repaired

    # Last resort: switch to a JSON-reliable NVIDIA model (still real_api)
    primary = (model or tf.model or DEFAULT_MODEL).strip()
    fallback = FALLBACK_INVESTIGATION_MODEL
    if primary == fallback:
        return repaired
    try:
        completion = tf.chat_completions(
            messages,
            model=fallback,
            temperature=0.0,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
    except NebiusAPIError as exc:
        return InvestigationResult(
            ok=False,
            evidence_class="api_error",
            recommendation=None,
            error=f"fallback {fallback} failed: {exc}",
            error_class=exc.error_class,
            http_status=exc.status_code,
            model=fallback,
            raw_content_preview=repaired.raw_content_preview,
        )
    out = _finalize_from_completion(
        completion,
        rule_fusion=ctx.rule_fusion,
        demo_mode=demo_mode,
        allow_containment_in_demo=allow_containment_in_demo,
        evidence_state=evidence_state,
    )
    if out.ok:
        out.gated_notes = list(out.gated_notes) + [f"fallback_model:{fallback}"]
    return out


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
    evidence_state: dict[str, Any] | None = None,
    camera: dict[str, Any] | None = None,
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
    estate = evidence_state
    if estate is None and camera is not None:
        estate = {"physical_sufficient": assess_physical_quality(camera).get("sufficient")}
    return _finalize_from_completion(
        fake,
        rule_fusion=rule_fusion,
        demo_mode=demo_mode,
        allow_containment_in_demo=allow_containment_in_demo,
        evidence_class_override=evidence_class,
        evidence_state=estate,
    )


def _finalize_from_completion(
    completion: ChatCompletionResult,
    *,
    rule_fusion: dict[str, Any] | None,
    demo_mode: bool,
    allow_containment_in_demo: bool,
    evidence_class_override: str | None = None,
    evidence_state: dict[str, Any] | None = None,
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
            evidence_state=evidence_state,
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
