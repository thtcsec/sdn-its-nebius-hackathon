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
from .input_sanitize import sanitize_camera, sanitize_telemetry
from .nebius_client import (
    DEFAULT_MODEL,
    NebiusAPIError,
    NebiusConfigError,
    NebiusTokenFactoryClient,
    load_api_key,
)
from .safety import gate_recommendation
from .schema import (
    ALLOWED_ACTIONS,
    MitigationRecommendation,
    RecommendationValidationError,
    extract_json_object,
    try_validate_recommendation,
    validate_recommendation,
)

PlannerMode = Literal["offline", "real"]
ConclusionKind = Literal["nemotron_conclude", "deterministic_fallback", "policy_overridden"]

# Bounded loop: reserve ≥1 model call for final reasoning after tools (not all spent on tool_call).
MAX_TOOLS_DEFAULT = 5
MAX_TOOL_MODEL_CALLS_DEFAULT = 3  # model tool_call rounds only
MAX_MODEL_CALLS_DEFAULT = 5  # ≤3 tool rounds + reserved conclude (+ optional repair)

AGENT_SYSTEM = """You are an SDN-ITS cyber-physical investigator for an ITS network operator / SOC analyst.
A traffic surge is not always an attack. Before disrupting a cyber-physical system, investigate the evidence.
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
- When uncertainties are listed, your FIRST reply MUST be action=tool_call (never conclude immediately).
- After tools return, you MUST conclude with action=conclude (do not keep calling tools forever).
- Choose the tool that addresses the most important missing evidence (quality, camera, contradiction, temporal).
- High road traffic does NOT prove a cyberattack is harmless — use identify_contradictions, then decide carefully.
- If physical evidence is insufficient/stale/unavailable, prefer observe; do not escalate containment.
- If telemetry_unreliable / NaN / non-numeric fields appear in tool results, you MUST conclude observe (fail closed). Never preserve_rush_hour or contain on bad numbers.
- If network attack label conflicts with rush-hour physical activity, prefer preserve_rush_hour or observe.
- If safety_critical / pedestrian / incident, prefer protect_safety.
- Never invent packet counters or claim live camera inference.
- Prefer escalate_human_review when still uncertain after tools.
- recommended_action must be exactly one of observe|rate_limit|temporary_drop|preserve_rush_hour|protect_safety — never placeholders like "...".
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
    # Who produced the advisory before/after gate (never claim fallback as nemotron_conclude)
    conclusion_kind: ConclusionKind | str = "deterministic_fallback"
    pre_gate_action: str | None = None
    pre_gate_source: str | None = None  # nemotron_conclude | deterministic_fallback
    pre_gate_recommendation: dict[str, Any] | None = None  # frozen advisory for paired gate replay

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
    tel = bundle.telemetry or {}
    q = bundle.physical_quality or (
        assess_physical_quality(cam) if bundle.include_camera else {"sufficient": False, "reasons": ["no_camera"]}
    )
    contradictions = list(bundle.contradictions)
    notes = [n for t in bundle.tool_results for n in t.evidence_notes][:10]

    if tel.get("_telemetry_unreliable") or tel.get("_sanitize_issues"):
        return {
            "recommended_action": "observe",
            "final_risk": "low",
            "rationale": "Untrusted/malformed telemetry fields — fail closed to observe (no containment).",
            "confidence": 0.2,
            "evidence_notes": notes + ["telemetry_unreliable", "fail_closed"],
            "false_positive_corrected": False,
            "safety_critical": False,
        }

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


def _schema_accept(rec_payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Accept model recommendation only after schema validation (+ safe aliases, never containment coercion)."""
    rec, err = try_validate_recommendation(rec_payload, allow_safe_alias=True)
    if rec is None:
        return None, err
    return rec.to_dict(), None


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
    pre_gate_source: str = "deterministic_fallback",
) -> MultiStepResult:
    try:
        rec = validate_recommendation(rec_payload)
    except RecommendationValidationError as exc:
        # Fail closed: no advisory recommendation; keep source label (do not claim Nemotron success)
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
            conclusion_kind="validation_error",
            pre_gate_source=pre_gate_source if pre_gate_source == "nemotron_conclude" else "deterministic_fallback",
            pre_gate_recommendation=dict(rec_payload) if isinstance(rec_payload, dict) else None,
            pre_gate_action=str((rec_payload or {}).get("recommended_action") or "") or None,
        )

    pre_gate_rec = rec.to_dict()
    pre_gate_action = rec.recommended_action
    notes: list[str] = []
    tel_unreliable = bool(
        (bundle.telemetry or {}).get("_telemetry_unreliable")
        or (bundle.telemetry or {}).get("_sanitize_issues")
        or "telemetry_unreliable" in (bundle.uncertainties or [])
    )
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
                "telemetry_unreliable": tel_unreliable,
            },
        )
        rec = gated
    else:
        notes.append("gate:skipped_ablation_arm")

    if apply_gate and rec.recommended_action != pre_gate_action:
        conclusion_kind: ConclusionKind | str = "policy_overridden"
    elif pre_gate_source == "nemotron_conclude":
        conclusion_kind = "nemotron_conclude"
    else:
        conclusion_kind = "deterministic_fallback"

    trace.append(
        TraceStep(
            "policy_gate",
            {
                "gated_notes": notes,
                "apply_gate": apply_gate,
                "pre_gate_action": pre_gate_action,
                "action": rec.recommended_action,
                "conclusion_kind": conclusion_kind,
            },
        )
    )
    trace.append(
        TraceStep(
            "audit",
            {
                "evidence_class": evidence_class,
                "tool_calls": tool_calls,
                "conclusion_kind": conclusion_kind,
                "pre_gate_source": pre_gate_source,
            },
        )
    )

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
        conclusion_kind=conclusion_kind,
        pre_gate_action=pre_gate_action,
        pre_gate_source=pre_gate_source,
        pre_gate_recommendation=pre_gate_rec,
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
    max_tool_model_calls: int = MAX_TOOL_MODEL_CALLS_DEFAULT,
    client: NebiusTokenFactoryClient | None = None,
    model: str | None = None,
) -> MultiStepResult:
    """Run bounded investigation loop. Never fabricates real_api evidence."""
    ensure_repo_env()
    t0 = time.perf_counter()
    tel_raw = dict(incident.get("telemetry") or {})
    cam_raw = dict(incident.get("camera") or {}) if include_camera else {}
    tel, tel_issues = sanitize_telemetry(tel_raw)
    cam, cam_issues = sanitize_camera(cam_raw) if include_camera else ({}, [])
    bundle = EvidenceBundle(
        incident_id=str(incident.get("id") or "unknown"),
        network_prediction=str(incident.get("network_prediction") or "Normal"),
        include_camera=include_camera,
        telemetry=tel,
        camera=cam,
        prior_windows=list(incident.get("prior_windows") or []),
    )
    if tel_issues or cam_issues:
        bundle.uncertainties = list(bundle.uncertainties) + (
            ["telemetry_unreliable"] if tel_issues else []
        ) + (["camera_fields_untrusted"] if cam_issues else [])
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
                conclusion_kind="deterministic_fallback",
            )

        def _one_completion(msgs: list[dict[str, str]]) -> Any:
            nonlocal model_calls, usage, cost, model_name, evidence_class
            try:
                completion = tf.chat_completions(
                    msgs,
                    model=model,
                    temperature=0.1,
                    max_tokens=768,
                    response_format={"type": "json_object"},
                )
            except NebiusAPIError as exc:
                if exc.status_code not in {400, 422}:
                    raise
                completion = tf.chat_completions(
                    msgs,
                    model=model,
                    temperature=0.1,
                    max_tokens=768,
                    response_format=None,
                )
            model_calls += 1
            evidence_class = "real_api"
            model_name = completion.model
            usage = _merge_usage(usage, completion.usage or {})
            cost += float(completion.estimated_cost_usd() or 0.0)
            return completion

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
                        "budget": {
                            "max_tool_model_calls": max_tool_model_calls,
                            "reserved_conclude_call": True,
                            "max_model_calls": max_model_calls,
                        },
                        "incident_stub": {
                            "id": bundle.incident_id,
                            "network_prediction": bundle.network_prediction,
                            "telemetry_keys": list(bundle.telemetry.keys()),
                            "camera_enabled": include_camera,
                        },
                        "instruction": (
                            "Uncertainties are open: your next JSON MUST be action=tool_call. "
                            "Do not conclude until at least one tool has returned evidence. "
                            f"You may call at most {max_tool_model_calls} tools, then you must conclude."
                            if uncertainties
                            else f"Select up to {max_tool_model_calls} tools, then conclude."
                        ),
                    },
                    indent=2,
                ),
            },
        ]

        concluded: dict[str, Any] | None = None
        pre_gate_source = "deterministic_fallback"
        require_tool_first = bool(uncertainties)
        tool_model_rounds = 0

        # Phase 1 — tool selection (hard-capped; never consume the reserved conclude slot)
        while (
            model_calls < max_model_calls - 1
            and tool_model_rounds < max_tool_model_calls
            and tool_calls < max_tools
            and concluded is None
        ):
            try:
                completion = _one_completion(messages)
            except NebiusAPIError as exc:
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
                    conclusion_kind="deterministic_fallback",
                )

            messages.append({"role": "assistant", "content": completion.content})
            try:
                obj = extract_json_object(completion.content)
            except RecommendationValidationError as exc:
                trace.append(TraceStep("reason", {"parse_error": str(exc), "preview": (completion.content or "")[:160]}))
                break

            action = str(obj.get("action") or "").strip()
            if action == "tool_call":
                tool = str(obj.get("tool") or "")
                tr = execute_tool(tool, bundle, dict(obj.get("args") or {}))
                tool_calls += 1
                tool_model_rounds += 1
                trace.append(
                    TraceStep(
                        "select_evidence_tool",
                        {
                            "tool": tool,
                            "tool_model_round": tool_model_rounds,
                            "max_tool_model_calls": max_tool_model_calls,
                        },
                    )
                )
                trace.append(TraceStep("retrieve_validate", tr.to_dict()))
                remaining_tools = max_tool_model_calls - tool_model_rounds
                messages.append(
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "tool_result": tr.to_dict(),
                                "uncertainties": identify_uncertainty(bundle),
                                "instruction": (
                                    "Tool budget exhausted for this investigation. "
                                    "Next reply MUST be action=conclude with a JSON recommendation."
                                    if remaining_tools <= 0
                                    else (
                                        f"You may call {remaining_tools} more tool(s), or conclude now. "
                                        "Prefer conclude once evidence is sufficient."
                                    )
                                ),
                            },
                            indent=2,
                            default=str,
                        ),
                    }
                )
                continue

            if action == "conclude" and isinstance(obj.get("recommendation"), dict):
                if require_tool_first and tool_calls == 0:
                    trace.append(
                        TraceStep(
                            "select_evidence_tool",
                            {
                                "rejected_premature_conclude": True,
                                "model_wanted_action": (obj.get("recommendation") or {}).get("recommended_action"),
                            },
                        )
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "notice": "Conclude rejected until at least one tool runs. Reply with action=tool_call.",
                                    "available_tools": tools,
                                    "uncertainties": uncertainties,
                                },
                                indent=2,
                            ),
                        }
                    )
                    continue
                accepted, schema_err = _schema_accept(dict(obj["recommendation"]))
                if accepted is None:
                    trace.append(
                        TraceStep(
                            "reason",
                            {
                                "rejected_invalid_conclude": True,
                                "phase": "during_tool_loop",
                                "error": schema_err,
                                "raw_action": (obj.get("recommendation") or {}).get("recommended_action"),
                            },
                        )
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"Invalid recommendation ({schema_err}). "
                                f"recommended_action MUST be one of {sorted(ALLOWED_ACTIONS)}. "
                                "Never use placeholders like '...'. Reply with action=conclude and a valid recommendation. "
                                "Do not invent containment actions outside the allow-list."
                            ),
                        }
                    )
                    continue
                concluded = accepted
                pre_gate_source = "nemotron_conclude"
                trace.append(
                    TraceStep(
                        "reason",
                        {
                            "source": "nemotron_conclude",
                            "phase": "during_tool_loop",
                            "preview": concluded,
                            "tool_calls_before_conclude": tool_calls,
                        },
                    )
                )
                break

            if "recommended_action" in obj and not (require_tool_first and tool_calls == 0):
                accepted, schema_err = _schema_accept(obj)
                if accepted is None:
                    trace.append(
                        TraceStep(
                            "reason",
                            {"rejected_invalid_bare_recommendation": True, "error": schema_err},
                        )
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"Invalid recommendation ({schema_err}). "
                                f"Use recommended_action in {sorted(ALLOWED_ACTIONS)} only."
                            ),
                        }
                    )
                    continue
                concluded = accepted
                pre_gate_source = "nemotron_conclude"
                trace.append(
                    TraceStep(
                        "reason",
                        {"source": "nemotron_bare_recommendation", "tool_calls": tool_calls},
                    )
                )
                break

            if "recommended_action" in obj and require_tool_first and tool_calls == 0:
                messages.append(
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "notice": "Recommendation rejected until you call a tool.",
                                "available_tools": tools,
                            },
                            indent=2,
                        ),
                    }
                )
                continue

            trace.append(TraceStep("reason", {"unexpected_in_tool_phase": obj}))
            break

        # Phase 2 — reserved final reasoning (model must conclude from gathered evidence)
        if concluded is None and tool_calls > 0 and model_calls < max_model_calls:
            evidence_pack = {
                "tool_results": [t.to_dict() for t in bundle.tool_results],
                "physical_sufficient": bundle.physical_sufficient,
                "physical_quality": bundle.physical_quality,
                "contradictions": bundle.contradictions,
                "human_escalation_requested": bundle.human_escalation_requested,
                "network_prediction": bundle.network_prediction,
                "include_camera": include_camera,
                "camera_note": "synthetic_metadata_only" if include_camera else "camera_ablation_disabled",
            }
            messages.append(
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "phase": "final_reason",
                            "notice": (
                                "Evidence gathering is complete. Do NOT call more tools. "
                                "Reply with action=conclude and a full recommendation JSON only."
                            ),
                            "evidence_pack": evidence_pack,
                        },
                        indent=2,
                        default=str,
                    ),
                }
            )
            trace.append(TraceStep("final_reason_prompt", {"reserved_conclude": True, "tool_calls": tool_calls}))
            for attempt in range(2):  # conclude + at most one schema/JSON repair
                if model_calls >= max_model_calls:
                    break
                try:
                    completion = _one_completion(messages)
                except NebiusAPIError as exc:
                    trace.append(TraceStep("reason", {"conclude_api_error": str(exc)}))
                    break
                messages.append({"role": "assistant", "content": completion.content})
                try:
                    obj = extract_json_object(completion.content)
                except RecommendationValidationError as exc:
                    trace.append(
                        TraceStep(
                            "reason",
                            {"conclude_parse_error": str(exc), "attempt": attempt, "preview": (completion.content or "")[:160]},
                        )
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Invalid JSON. Reply again with ONLY "
                                '{"action":"conclude","recommendation":{'
                                f'"recommended_action": one of {sorted(ALLOWED_ACTIONS)}, '
                                '"final_risk":"low|medium|high|critical","rationale":"...",'
                                '"confidence":0.0,"evidence_notes":[]}}'
                            ),
                        }
                    )
                    continue
                if str(obj.get("action") or "") == "tool_call":
                    trace.append(TraceStep("reason", {"rejected_tool_in_conclude_phase": obj.get("tool")}))
                    messages.append(
                        {
                            "role": "user",
                            "content": "Tools are closed. Reply with action=conclude only.",
                        }
                    )
                    continue
                rec_obj = obj.get("recommendation") if str(obj.get("action") or "") == "conclude" else obj
                if isinstance(rec_obj, dict) and rec_obj.get("recommended_action") is not None:
                    accepted, schema_err = _schema_accept(dict(rec_obj))
                    if accepted is None:
                        trace.append(
                            TraceStep(
                                "reason",
                                {
                                    "conclude_schema_error": schema_err,
                                    "attempt": attempt,
                                    "raw_action": rec_obj.get("recommended_action"),
                                    "note": "No containment coercion from unknown/placeholder actions",
                                },
                            )
                        )
                        if attempt == 0:
                            messages.append(
                                {
                                    "role": "user",
                                    "content": (
                                        f"Schema validation failed: {schema_err}. "
                                        f"Repair once: recommended_action MUST be exactly one of {sorted(ALLOWED_ACTIONS)}. "
                                        "Never use '...', null, or free-text verbs. "
                                        "If uncertain, use observe. Do not invent new containment actions."
                                    ),
                                }
                            )
                            continue
                        # Repair exhausted — do not accept invalid model conclusion
                        break
                    concluded = accepted
                    pre_gate_source = "nemotron_conclude"
                    trace.append(
                        TraceStep(
                            "reason",
                            {
                                "source": "nemotron_conclude",
                                "phase": "reserved_final_reason",
                                "preview": concluded,
                                "tool_calls_before_conclude": tool_calls,
                                "repair_attempt": attempt,
                            },
                        )
                    )
                    break
                trace.append(TraceStep("reason", {"conclude_unexpected": obj, "attempt": attempt}))
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            'Reply with {"action":"conclude","recommendation":{...}} only. '
                            f"recommended_action in {sorted(ALLOWED_ACTIONS)}."
                        ),
                    }
                )

        if concluded is None:
            concluded = evidence_based_recommend(bundle)
            pre_gate_source = "deterministic_fallback"
            trace.append(
                TraceStep(
                    "reason",
                    {
                        "source": "deterministic_fallback",
                        "note": (
                            "Used only after reserved conclude phase failed, schema rejected "
                            "(incl. placeholder actions like '...'), or no tools ran. "
                            "Not labeled as nemotron_conclude."
                        ),
                    },
                )
            )

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
            pre_gate_source=pre_gate_source,
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
        pre_src = "deterministic_fallback"
        trace.append(TraceStep("reason", {"source": "synthetic_offline_fixture"}))
    else:
        concluded = evidence_based_recommend(bundle)
        evidence_class = "deterministic_planner"
        planner = "deterministic"
        pre_src = "deterministic_fallback"
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
        pre_gate_source=pre_src,
    )
