"""Cyber–physical incident investigation agent (rule baseline ⊕ Nemotron advisory)."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from sdn_its.camera.fusion import FusionEngine
from sdn_its.controller.flow_manager import FlowRuleManager
from sdn_its.llm.audit_log import record_audit
from sdn_its.llm.investigation import (
    IncidentContext,
    InvestigationResult,
    investigate_from_model_text,
    investigate_incident,
)
from sdn_its.mitigation.policy_engine import PolicyEngine
from sdn_its.utils.env import ensure_repo_env

Mode = Literal["offline", "real"]


CONTAINMENT = frozenset({"rate_limit", "temporary_drop"})


@dataclass
class PathResult:
    path: str  # rule_only | nemotron_assisted
    recommended_action: str | None
    policy_status: str | None
    applied_rules_count: int = 0
    final_risk: str | None = None
    rationale: str | None = None
    evidence_class: str | None = None
    gated_notes: list[str] = field(default_factory=list)
    latency_ms: float | None = None
    usage: dict[str, int] = field(default_factory=dict)
    estimated_cost_usd: float | None = None
    ok: bool = True
    error: str | None = None
    fusion: dict[str, Any] | None = None
    raw_preview: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InvestigationCaseResult:
    incident_id: str
    title: str
    mode: str
    telemetry: dict[str, Any]
    camera: dict[str, Any]
    network_prediction: str
    rule: PathResult
    nemotron: PathResult
    metrics: dict[str, Any]
    of_backend: str = "mock"
    demo_mode: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "title": self.title,
            "mode": self.mode,
            "network_prediction": self.network_prediction,
            "telemetry": self.telemetry,
            "camera": self.camera,
            "rule": self.rule.to_dict(),
            "nemotron": self.nemotron.to_dict(),
            "metrics": self.metrics,
            "of_backend": self.of_backend,
            "demo_mode": self.demo_mode,
            "note": (
                "Nemotron path is advisory. Deterministic FusionEngine + safety gate + "
                "PolicyEngine remain authoritative. Default OpenFlow backend is mock."
            ),
        }


def _policy_apply(network_prediction: str, dpid: str, src_ip: str, fusion: dict[str, Any]) -> tuple[str, int]:
    eng = PolicyEngine(FlowRuleManager(of_push_callback=None).containment)
    mit = eng.apply(network_prediction, dpid=dpid, src_ip=src_ip, fusion=fusion)
    return mit.mitigation_status, len(mit.applied_rules)


def run_rule_only(incident: dict[str, Any]) -> PathResult:
    t0 = time.perf_counter()
    tel = dict(incident.get("telemetry") or {})
    cam = dict(incident.get("camera") or {})
    net = str(incident.get("network_prediction") or "Normal")
    fusion = FusionEngine().fuse(
        network_prediction=net,
        physical=cam,
        source_dominance=tel.get("source_dominance"),
        distributed_sources=tel.get("distributed_sources"),
        packet_in_delta_pct=tel.get("packet_in_delta_pct"),
    )
    fus = fusion.to_dict()
    status, n_rules = _policy_apply(
        net,
        str(incident.get("dpid") or "1"),
        str(incident.get("src_ip") or "10.0.0.15"),
        fus,
    )
    return PathResult(
        path="rule_only",
        recommended_action=fusion.recommended_action,
        policy_status=status,
        applied_rules_count=n_rules,
        final_risk=fusion.final_risk,
        rationale=fusion.explain,
        evidence_class="deterministic_rules",
        latency_ms=(time.perf_counter() - t0) * 1000.0,
        ok=True,
        fusion=fus,
    )


def run_nemotron_path(
    incident: dict[str, Any],
    *,
    mode: Mode,
    demo_mode: bool = True,
    allow_containment_in_demo: bool = False,
    rule_fusion: dict[str, Any] | None = None,
) -> PathResult:
    ensure_repo_env()
    force = incident.get("force_mode")
    tel = dict(incident.get("telemetry") or {})
    cam = dict(incident.get("camera") or {})
    net = str(incident.get("network_prediction") or "Normal")
    ctx = IncidentContext(
        network_prediction=net,
        telemetry=tel,
        camera=cam,
        rule_fusion=rule_fusion,
        dpid=str(incident.get("dpid") or "1"),
        src_ip=str(incident.get("src_ip") or "10.0.0.15"),
    )

    t0 = time.perf_counter()
    result: InvestigationResult

    if force == "unavailable_api" or (mode == "offline" and force == "unavailable_api"):
        prev = os.environ.get("NEBIUS_API_KEY")
        os.environ["NEBIUS_API_KEY"] = ""
        try:
            result = investigate_incident(
                ctx,
                demo_mode=demo_mode,
                allow_containment_in_demo=allow_containment_in_demo,
            )
        finally:
            if prev is None:
                os.environ.pop("NEBIUS_API_KEY", None)
            else:
                os.environ["NEBIUS_API_KEY"] = prev
    elif force == "malformed_synthetic" or (
        mode == "offline" and isinstance(incident.get("synthetic_model_output_raw"), str)
    ):
        raw = str(incident.get("synthetic_model_output_raw") or "")
        result = investigate_from_model_text(
            raw,
            rule_fusion=rule_fusion,
            demo_mode=demo_mode,
            allow_containment_in_demo=allow_containment_in_demo,
            evidence_class="synthetic_malformed",
            camera=cam,
        )
    elif mode == "offline" or force == "synthetic_json" or incident.get("synthetic_model_output"):
        payload = incident.get("synthetic_model_output")
        if not isinstance(payload, dict):
            return PathResult(
                path="nemotron_assisted",
                recommended_action=None,
                policy_status=None,
                ok=False,
                evidence_class="offline_missing_synthetic",
                error="offline mode requires synthetic_model_output",
                latency_ms=(time.perf_counter() - t0) * 1000.0,
            )
        result = investigate_from_model_text(
            json.dumps(payload),
            rule_fusion=rule_fusion,
            demo_mode=demo_mode,
            allow_containment_in_demo=allow_containment_in_demo,
            evidence_class="synthetic_offline",
            camera=cam,
        )
    else:
        result = investigate_incident(
            ctx,
            demo_mode=demo_mode,
            allow_containment_in_demo=allow_containment_in_demo,
        )

    latency = result.latency_ms if result.latency_ms is not None else (time.perf_counter() - t0) * 1000.0
    if not result.ok or result.fusion_for_policy is None:
        return PathResult(
            path="nemotron_assisted",
            recommended_action=None,
            policy_status=None,
            ok=False,
            evidence_class=result.evidence_class,
            gated_notes=list(result.gated_notes),
            latency_ms=latency,
            usage=dict(result.usage or {}),
            estimated_cost_usd=result.estimated_cost_usd,
            error=result.error,
            raw_preview=result.raw_content_preview,
        )

    status, n_rules = _policy_apply(net, ctx.dpid, ctx.src_ip, result.fusion_for_policy)
    rec = result.recommendation
    return PathResult(
        path="nemotron_assisted",
        recommended_action=rec.recommended_action if rec else None,
        policy_status=status,
        applied_rules_count=n_rules,
        final_risk=rec.final_risk if rec else None,
        rationale=rec.rationale if rec else None,
        evidence_class=result.evidence_class,
        gated_notes=list(result.gated_notes),
        latency_ms=latency,
        usage=dict(result.usage or {}),
        estimated_cost_usd=result.estimated_cost_usd,
        ok=True,
        fusion=result.fusion_for_policy,
        raw_preview=result.raw_content_preview,
    )


def score_case(incident: dict[str, Any], rule: PathResult, nemotron: PathResult) -> dict[str, Any]:
    expected = dict(incident.get("expected") or {})
    rule_ok = rule.recommended_action in set(expected.get("rule_action_in") or []) if rule.ok else False
    agreement = bool(
        rule.ok
        and nemotron.ok
        and rule.recommended_action
        and rule.recommended_action == nemotron.recommended_action
    )
    inappropriate = False
    if nemotron.ok and nemotron.recommended_action in CONTAINMENT:
        if expected.get("allow_containment") is False:
            inappropriate = True
    gate_blocked = any(
        n.startswith("gate:deescalated") or n.startswith("gate:forced") or "demo_block" in n
        for n in (nemotron.gated_notes or [])
    )
    if expected.get("gate_must_block_escalation") and not gate_blocked and nemotron.ok:
        # If model wanted drop but ended observe/protect, still count as blocked outcome
        if nemotron.recommended_action not in CONTAINMENT:
            gate_blocked = True
    abstained = bool(nemotron.ok and nemotron.recommended_action == "observe") or (
        not nemotron.ok and nemotron.evidence_class in {"validation_error", "blocked_no_credentials", "synthetic_malformed"}
    )
    validation_failed = nemotron.evidence_class in {"validation_error", "synthetic_malformed"} or (
        expected.get("nemotron_must_fail_validation") and not nemotron.ok
    )
    api_blocked = nemotron.evidence_class == "blocked_no_credentials"
    return {
        "rule_matches_expected": rule_ok,
        "decision_agreement": agreement,
        "inappropriate_containment": inappropriate,
        "escalation_or_demo_gate_fired": gate_blocked,
        "abstention_or_fail_closed": abstained,
        "validation_failed_as_expected": bool(expected.get("nemotron_must_fail_validation")) == validation_failed
        if expected.get("nemotron_must_fail_validation")
        else None,
        "api_unavailable_as_expected": (
            api_blocked if expected.get("nemotron_evidence_class") == "blocked_no_credentials" else None
        ),
        "gate_block_as_expected": (
            gate_blocked if expected.get("gate_must_block_escalation") else None
        ),
    }


def investigate_case(
    incident: dict[str, Any],
    *,
    mode: Mode = "offline",
    demo_mode: bool = True,
    allow_containment_in_demo: bool = False,
    record: bool = True,
    multi_step: bool = False,
) -> InvestigationCaseResult:
    rule = run_rule_only(incident)
    if multi_step:
        from sdn_its.llm.ablation import run_ablation_arm

        nemotron = run_ablation_arm(
            incident,
            "D_net_cam_gate",
            mode=mode,
            demo_mode=demo_mode,
            allow_containment_in_demo=allow_containment_in_demo,
        )
        nemotron.path = "nemotron_multistep"
    else:
        nemotron = run_nemotron_path(
            incident,
            mode=mode,
            demo_mode=demo_mode,
            allow_containment_in_demo=allow_containment_in_demo,
            rule_fusion=rule.fusion,
        )
    metrics = score_case(incident, rule, nemotron)
    metrics["rule_latency_ms"] = rule.latency_ms
    metrics["nemotron_latency_ms"] = nemotron.latency_ms
    metrics["estimated_cost_usd"] = nemotron.estimated_cost_usd
    metrics["multi_step"] = multi_step
    if multi_step and isinstance(nemotron.fusion, dict):
        metrics["tool_calls"] = nemotron.fusion.get("tool_calls")
        metrics["model_calls"] = nemotron.fusion.get("model_calls")
    case = InvestigationCaseResult(
        incident_id=str(incident.get("id")),
        title=str(incident.get("title") or incident.get("id")),
        mode=mode,
        telemetry=dict(incident.get("telemetry") or {}),
        camera=dict(incident.get("camera") or {}),
        network_prediction=str(incident.get("network_prediction") or "Normal"),
        rule=rule,
        nemotron=nemotron,
        metrics=metrics,
        demo_mode=demo_mode,
    )
    if record:
        record_audit(
            {
                "incident_id": case.incident_id,
                "mode": mode,
                "multi_step": multi_step,
                "rule_action": rule.recommended_action,
                "rule_policy": rule.policy_status,
                "nemotron_action": nemotron.recommended_action,
                "nemotron_policy": nemotron.policy_status,
                "nemotron_evidence_class": nemotron.evidence_class,
                "gated_notes": nemotron.gated_notes,
                "metrics": metrics,
                "rationale_preview": (nemotron.rationale or "")[:180],
                "trace_preview": (
                    (nemotron.fusion or {}).get("trace", [])[:6] if isinstance(nemotron.fusion, dict) else []
                ),
            }
        )
    return case
