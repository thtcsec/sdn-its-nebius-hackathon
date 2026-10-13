"""Bounded multi-step cyber–physical investigation loop.

DETECT → IDENTIFY UNCERTAINTY → SELECT EVIDENCE TOOL → RETRIEVE → REASON → POLICY GATE → AUDIT

Offline mode uses a deterministic planner + evidence-based recommender
(evidence_class=deterministic_planner) — never presented as live Nemotron.
Real mode uses Nebius Token Factory for tool selection and final reasoning.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from sdn_its.utils.env import ensure_repo_env

from .evidence_tools import (
    EvidenceBundle,
    assess_physical_quality,
    default_tool_plan,
    execute_tool,
    identify_uncertainty,
    list_tools,
)
from .nebius_client import (
    DEFAULT_MODEL,
    NebiusAPIError,
    NebiusConfigError,
    NebiusTokenFactoryClient,
    load_api_key,
)
from .safety import gate_recommendation
from .schema import (
    MitigationRecommendation,
    RecommendationValidationError,
    extract_json_object,
    validate_recommendation,
)

PlannerMode = Literal["offline", "real"]

MAX_TOOLS_DEFAULT = 5
MAX_MODEL_CALLS_DEFAULT = 3

AGENT_SYSTEM = """You are an SDN-ITS cyber-physical investigator.
A network traffic surge is not always an attack — gather physical context before disruptive decisions.
You do NOT execute OpenFlow. You may only call evidence tools or conclude.

Reply with ONE JSON object only (no markdown, no chain-of-thought):

Tool call:
{"action":"tool_call","tool":"<name>","args":{}}

Final recommendation:
{"action":"conclude","recommendation":{
  "recommended_action":"observe|rate_limit|temporary_drop|preserve_rush_hour|protect_safety",
  "final_risk":"low|medium|high|critical",
  "rationale":"...",
  "policy_attack_type":null,
  "cooldown_seconds":15,
  "false_positive_corrected":false,
  "safety_critical":false,
  "confidence":0.0,
  "evidence_notes":[]
}}

Rules:
- If physical evidence is insufficient/stale/unavailable, prefer observe; do not escalate containment.
- If network attack label conflicts with rush-hour physical activity, prefer preserve_rush_hour or observe.
- If safety_critical / pedestrian / incident, prefer protect_safety.
- Never invent packet counters or claim live camera inference.
- Prefer escalate_human_review tool when uncertain.
"""


@dataclass
class TraceStep:
    phase: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"phase": self.phase, "detail": self.detail}


@dataclass
class MultiStepResult:
    ok: bool
    evidence_class: str
    recommendation: MitigationRecommendation | None
    gated_notes: list[str] = field(default_factory=list)
    fusion_for_policy: dict[str, Any] | None = None
    trace: list[TraceStep] = field(default_factory=list)
    tool_calls: int = 0
    model_calls: int = 0
    usage: dict[str, int] = field(default_factory=dict)
    estimated_cost_usd: float | None = None
    latency_ms: float | None = None
    model: str | None = None
    error: str | None = None
    bundle: dict[str, Any] = field(default_factory=dict)
    apply_gate: bool = True
    include_camera: bool = True
    planner: str = "deterministic"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.recommendation is not None:
            d["recommendation"] = self.recommendation.to_dict()
        d["trace"] = [t.to_dict() for t in self.trace]
        return d


def _merge_usage(a: dict[str, int], b: dict[str, int]) -> dict[str, int]:
    out = dict(a)
    for k, v in b.items():
        out[k] = int(out.get(k, 0)) + int(v or 0)
    return out


def evidence_based_recommend(bundle: EvidenceBundle) -> dict[str, Any]:
    """Deterministic conclude step for offline / fail-closed paths (not live Nemotron)."""
    net = bundle.network_prediction
    cam = bundle.camera if bundle.include_camera else {}
    q = bundle.physical_quality or (
        assess_physical_quality(cam) if bundle.include_camera else {"sufficient": False, "reasons": ["no_camera"]}
    )
    contradictions = list(bundle.contradictions)
    notes = [n for t in bundle.tool_results for n in t.evidence_notes][:10]

    if bool(cam.get("incident")) or bool(cam.get("pedestrian_present")) or bool(cam.get("safety_critical")):
        return {
            "recommended_action": "protect_safety",
            "final_risk": "critical",
            "rationale": "Physical safety signal present; protect road users before cyber containment.",
            "policy_attack_type": net,
            "cooldown_seconds": 15,
            "false_positive_corrected": False,
            "safety_critical": True,
            "confidence": 0.85,
            "evidence_notes": notes + ["safety_physical"],
        }

    if bundle.human_escalation_requested or not q.get("sufficient"):
        return {
            "recommended_action": "observe",
            "final_risk": "medium",
            "rationale": (
                "Physical evidence insufficient, stale, or human review requested; "
                "do not escalate containment on network anomaly alone."
            ),
            "policy_attack_type": net,
            "cooldown_seconds": 15,
            "false_positive_corrected": True,
            "safety_critical": False,
            "confidence": 0.55,
            "evidence_notes": notes + ["abstain_insufficient_evidence"],
        }

    if "network_attack_label_vs_rush_physical" in contradictions or "ddos_vs_long_queue" in contradictions:
        return {
            "recommended_action": "preserve_rush_hour",
            "final_risk": "medium",
            "rationale": "Network attack label conflicts with rush/queue physical context; preserve mobility.",
            "policy_attack_type": "RushHour_Burst",
            "cooldown_seconds": 15,
            "false_positive_corrected": True,
            "safety_critical": False,
            "confidence": 0.7,
            "evidence_notes": notes + contradictions,
        }

    if net == "RushHour_Burst":
        return {
            "recommended_action": "preserve_rush_hour",
            "final_risk": "low",
            "rationale": "Rush-hour burst with usable physical corroboration; avoid disruptive containment.",
            "policy_attack_type": "RushHour_Burst",
            "cooldown_seconds": 15,
            "false_positive_corrected": True,
            "safety_critical": False,
            "confidence": 0.75,
            "evidence_notes": notes,
        }

    if net == "LOFT_LowRate_Attack" and q.get("sufficient"):
        label = str(cam.get("physical_label") or "")
        if label in {"stable", "quiet", "empty", "normal"}:
            return {
                "recommended_action": "rate_limit",
                "final_risk": "medium",
                "rationale": "Low-rate anomaly with stable physical context supports soft rate-limit.",
                "policy_attack_type": "LOFT_LowRate_Attack",
                "cooldown_seconds": 15,
                "false_positive_corrected": False,
                "safety_critical": False,
                "confidence": 0.65,
                "evidence_notes": notes,
            }

    if net == "DDoS_PacketIn_Flood" and q.get("sufficient"):
        label = str(cam.get("physical_label") or "")
        if label in {"stable", "quiet", "empty", "normal"}:
            return {
                "recommended_action": "rate_limit",
                "final_risk": "high",
                "rationale": "High PacketIn with quiet physical zone; soft containment pending human review.",
                "policy_attack_type": "DDoS_PacketIn_Flood",
                "cooldown_seconds": 20,
                "false_positive_corrected": False,
                "safety_critical": False,
                "confidence": 0.6,
                "evidence_notes": notes + ["prefer_soft_over_drop"],
            }

    return {
        "recommended_action": "observe",
        "final_risk": "low",
        "rationale": "Evidence gathered; residual uncertainty → observe.",
        "policy_attack_type": net,
        "cooldown_seconds": 15,
        "false_positive_corrected": False,
        "safety_critical": False,
        "confidence": 0.5,
        "evidence_notes": notes + ["default_observe"],
    }


def _finalize(
    rec_payload: dict[str, Any],
    *,
    rule_fusion: dict[str, Any] | None,
    demo_mode: bool,
    allow_containment_in_demo: bool,
    apply_gate: bool,
    bundle: EvidenceBundle,
    evidence_class: str,
    usage: dict[str, int],
    cost: float | None,
    latency_ms: float,
    model: str | None,
    trace: list[TraceStep],
    tool_calls: int,
    model_calls: int,
    planner: str,
) -> MultiStepResult:
    try:
        rec = validate_recommendation(rec_payload)
    except RecommendationValidationError as exc:
        return MultiStepResult(
            ok=False,
            evidence_class="validation_error",
            recommendation=None,
            error=str(exc),
            trace=trace,
            tool_calls=tool_calls,
            model_calls=model_calls,
            usage=usage,
            estimated_cost_usd=cost,
            latency_ms=latency_ms,
            model=model,
            bundle=bundle.to_dict(),
            apply_gate=apply_gate,
            include_camera=bundle.include_camera,
            planner=planner,
        )

    notes: list[str] = []
    if apply_gate:
        gated, notes = gate_recommendation(
            rec,
            rule_fusion=rule_fusion,
            demo_mode=demo_mode,
            allow_containment_in_demo=allow_containment_in_demo,
            evidence_state={
                "physical_sufficient": bundle.physical_sufficient,
                "human_escalation_requested": bundle.human_escalation_requested,
                "include_camera": bundle.include_camera,
            },
        )
        rec = gated
    else:
        notes.append("gate:skipped_ablation_arm")

    trace.append(TraceStep("policy_gate", {"gated_notes": notes, "apply_gate": apply_gate, "action": rec.recommended_action}))
    trace.append(TraceStep("audit", {"evidence_class": evidence_class, "tool_calls": tool_calls}))

    return MultiStepResult(
        ok=True,
        evidence_class=evidence_class,
        recommendation=rec,
        gated_notes=notes,
        fusion_for_policy=rec.to_fusion_dict(),
        trace=trace,
        tool_calls=tool_calls,
        model_calls=model_calls,
        usage=usage,
        estimated_cost_usd=cost,
        latency_ms=latency_ms,
        model=model,
        bundle=bundle.to_dict(),
        apply_gate=apply_gate,
        include_camera=bundle.include_camera,
        planner=planner,
    )


def run_multi_step_investigation(
    incident: dict[str, Any],
    *,
    mode: PlannerMode = "offline",
    include_camera: bool = True,
    apply_gate: bool = True,
    demo_mode: bool = True,
    allow_containment_in_demo: bool = False,
    rule_fusion: dict[str, Any] | None = None,
    max_tools: int = MAX_TOOLS_DEFAULT,
    max_model_calls: int = MAX_MODEL_CALLS_DEFAULT,
    client: NebiusTokenFactoryClient | None = None,
    model: str | None = None,
) -> MultiStepResult:
    """Run bounded investigation loop. Never fabricates real_api evidence."""
    ensure_repo_env()
    t0 = time.perf_counter()
    cam = dict(incident.get("camera") or {}) if include_camera else {}
    bundle = EvidenceBundle(
        incident_id=str(incident.get("id") or "unknown"),
        network_prediction=str(incident.get("network_prediction") or "Normal"),
        include_camera=include_camera,
        telemetry=dict(incident.get("telemetry") or {}),
        camera=cam,
        prior_windows=list(incident.get("prior_windows") or []),
    )
    trace: list[TraceStep] = []
    trace.append(
        TraceStep(
            "detect",
            {
                "network_prediction": bundle.network_prediction,
                "incident_id": bundle.incident_id,
                "include_camera": include_camera,
            },
        )
    )
    uncertainties = identify_uncertainty(bundle)
    trace.append(TraceStep("identify_uncertainty", {"uncertainties": uncertainties}))

    usage: dict[str, int] = {}
    cost = 0.0
    model_calls = 0
    tool_calls = 0
    model_name: str | None = None
    evidence_class = "deterministic_planner"
    planner = "deterministic"

    # Protocol: unavailable API
    if incident.get("force_mode") == "unavailable_api":
        trace.append(TraceStep("api_unavailable", {"evidence_class": "blocked_no_credentials"}))
        return MultiStepResult(
            ok=False,
            evidence_class="blocked_no_credentials",
            recommendation=None,
            error="NEBIUS_API_KEY unavailable (protocol probe)",
            trace=trace,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            bundle=bundle.to_dict(),
            apply_gate=apply_gate,
            include_camera=include_camera,
            planner="none",
        )

    # Protocol: malformed — still run tools, then fail validation on conclude
    if incident.get("force_mode") == "malformed_synthetic" or (
        mode == "offline" and isinstance(incident.get("synthetic_model_output_raw"), str)
    ):
        for name in default_tool_plan(bundle)[:max_tools]:
            args = {"reason": "physical_evidence_gap"} if name == "escalate_human_review" else {}
            tr = execute_tool(name, bundle, args)
            tool_calls += 1
            trace.append(TraceStep("retrieve_validate", tr.to_dict()))
        raw = str(incident.get("synthetic_model_output_raw") or "{not-json")
        trace.append(TraceStep("reason", {"raw_preview": raw[:120], "forced": "malformed"}))
        return MultiStepResult(
            ok=False,
            evidence_class="synthetic_malformed",
            recommendation=None,
            error="malformed model output (protocol)",
            trace=trace,
            tool_calls=tool_calls,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            bundle=bundle.to_dict(),
            apply_gate=apply_gate,
            include_camera=include_camera,
            planner="protocol",
        )

    if mode == "real":
        planner = "nemotron"
        try:
            tf = client or NebiusTokenFactoryClient(model=model or DEFAULT_MODEL)
            load_api_key(tf.api_key)
        except NebiusConfigError as exc:
            return MultiStepResult(
                ok=False,
                evidence_class="blocked_no_credentials",
                recommendation=None,
                error=str(exc),
                trace=trace,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                bundle=bundle.to_dict(),
                apply_gate=apply_gate,
                include_camera=include_camera,
                planner=planner,
            )

        tools = list_tools(include_camera=include_camera)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": AGENT_SYSTEM},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "phase": "investigate",
                        "available_tools": tools,
                        "uncertainties": uncertainties,
                        "incident_stub": {
                            "id": bundle.incident_id,
                            "network_prediction": bundle.network_prediction,
                            "telemetry_keys": list(bundle.telemetry.keys()),
                            "camera_enabled": include_camera,
                        },
                        "instruction": "Select a tool or conclude. Prefer tools before concluding.",
                    },
                    indent=2,
                ),
            },
        ]

        concluded: dict[str, Any] | None = None
        while model_calls < max_model_calls and tool_calls <= max_tools:
            try:
                completion = tf.chat_completions(
                    messages,
                    model=model,
                    temperature=0.1,
                    max_tokens=768,
                    response_format={"type": "json_object"},
                )
            except NebiusAPIError as exc:
                if exc.status_code in {400, 422}:
                    try:
                        completion = tf.chat_completions(
                            messages,
                            model=model,
                            temperature=0.1,
                            max_tokens=768,
                            response_format=None,
                        )
                    except NebiusAPIError as exc2:
                        return MultiStepResult(
                            ok=False,
                            evidence_class="api_error",
                            recommendation=None,
                            error=str(exc2),
                            trace=trace,
                            tool_calls=tool_calls,
                            model_calls=model_calls,
                            usage=usage,
                            estimated_cost_usd=cost or None,
                            latency_ms=(time.perf_counter() - t0) * 1000.0,
                            bundle=bundle.to_dict(),
                            apply_gate=apply_gate,
                            include_camera=include_camera,
                            planner=planner,
                        )
                else:
                    return MultiStepResult(
                        ok=False,
                        evidence_class="api_error",
                        recommendation=None,
                        error=str(exc),
                        trace=trace,
                        tool_calls=tool_calls,
                        model_calls=model_calls,
                        usage=usage,
                        estimated_cost_usd=cost or None,
                        latency_ms=(time.perf_counter() - t0) * 1000.0,
                        bundle=bundle.to_dict(),
                        apply_gate=apply_gate,
                        include_camera=include_camera,
                        planner=planner,
                    )

            model_calls += 1
            evidence_class = "real_api"
            model_name = completion.model
            usage = _merge_usage(usage, completion.usage or {})
            cost += float(completion.estimated_cost_usd() or 0.0)
            messages.append({"role": "assistant", "content": completion.content})
            try:
                obj = extract_json_object(completion.content)
            except RecommendationValidationError as exc:
                trace.append(TraceStep("reason", {"parse_error": str(exc), "preview": (completion.content or "")[:160]}))
                break

            action = str(obj.get("action") or "").strip()
            if action == "tool_call":
                tool = str(obj.get("tool") or "")
                if tool_calls >= max_tools:
                    trace.append(TraceStep("select_evidence_tool", {"blocked": "max_tools", "tool": tool}))
                    break
                tr = execute_tool(tool, bundle, dict(obj.get("args") or {}))
                tool_calls += 1
                trace.append(TraceStep("select_evidence_tool", {"tool": tool}))
                trace.append(TraceStep("retrieve_validate", tr.to_dict()))
                messages.append(
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "tool_result": tr.to_dict(),
                                "uncertainties": identify_uncertainty(bundle),
                                "instruction": "Call another tool or conclude with JSON recommendation.",
                            },
                            indent=2,
                            default=str,
                        ),
                    }
                )
                continue
            if action == "conclude" and isinstance(obj.get("recommendation"), dict):
                concluded = dict(obj["recommendation"])
                trace.append(TraceStep("reason", {"source": "nemotron_conclude", "preview": concluded}))
                break
            # Tolerate bare recommendation objects
            if "recommended_action" in obj:
                concluded = obj
                trace.append(TraceStep("reason", {"source": "nemotron_bare_recommendation"}))
                break
            trace.append(TraceStep("reason", {"unexpected": obj}))
            break

        if concluded is None:
            # Fail soft: deterministic conclude from gathered evidence (still real_api tools path)
            concluded = evidence_based_recommend(bundle)
            trace.append(TraceStep("reason", {"source": "fallback_evidence_recommender_after_real_api"}))
            # Keep evidence_class real_api if we paid for calls; note hybrid
            if model_calls:
                trace.append(TraceStep("audit", {"hybrid_conclude": True}))

        return _finalize(
            concluded,
            rule_fusion=rule_fusion,
            demo_mode=demo_mode,
            allow_containment_in_demo=allow_containment_in_demo,
            apply_gate=apply_gate,
            bundle=bundle,
            evidence_class=evidence_class,
            usage=usage,
            cost=cost if model_calls else None,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            model=model_name,
            trace=trace,
            tool_calls=tool_calls,
            model_calls=model_calls,
            planner=planner,
        )

    # Offline: deterministic planner + real tool execution + evidence recommender
    # Optional synthetic conclude override labeled synthetic_offline (never as real_api)
    plan = default_tool_plan(bundle)[:max_tools]
    for name in plan:
        args = {"reason": "insufficient_or_conflicting_evidence"} if name == "escalate_human_review" else {}
        tr = execute_tool(name, bundle, args)
        tool_calls += 1
        trace.append(TraceStep("select_evidence_tool", {"tool": name, "planner": "deterministic"}))
        trace.append(TraceStep("retrieve_validate", tr.to_dict()))

    if incident.get("synthetic_model_output") and incident.get("force_mode") == "synthetic_json":
        concluded = dict(incident["synthetic_model_output"])
        evidence_class = "synthetic_offline"
        planner = "synthetic_fixture"
        trace.append(TraceStep("reason", {"source": "synthetic_offline_fixture"}))
    else:
        concluded = evidence_based_recommend(bundle)
        evidence_class = "deterministic_planner"
        planner = "deterministic"
        trace.append(TraceStep("reason", {"source": "evidence_based_recommender", "recommendation": concluded}))

    return _finalize(
        concluded,
        rule_fusion=rule_fusion,
        demo_mode=demo_mode,
        allow_containment_in_demo=allow_containment_in_demo,
        apply_gate=apply_gate,
        bundle=bundle,
        evidence_class=evidence_class,
        usage=usage,
        cost=None,
        latency_ms=(time.perf_counter() - t0) * 1000.0,
        model=None,
        trace=trace,
        tool_calls=tool_calls,
        model_calls=0,
        planner=planner,
    )
