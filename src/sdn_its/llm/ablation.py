"""Fair ablation arms on identical evaluation inputs.

A — rule_only
B — nemotron/planner network telemetry only (multi-step, gated)
C — network + camera multi-step (no safety gate; schema still validated)
D — network + camera multi-step + deterministic safety gate
"""

from __future__ import annotations

from typing import Any, Literal

from .agent import PathResult, _policy_apply, run_rule_only
from .multi_step import run_multi_step_investigation

Arm = Literal["A_rule_only", "B_net_only", "C_net_cam", "D_net_cam_gate"]


def run_ablation_arm(
    incident: dict[str, Any],
    arm: Arm,
    *,
    mode: Literal["offline", "real"] = "offline",
    demo_mode: bool = True,
    allow_containment_in_demo: bool = False,
) -> PathResult:
    if arm == "A_rule_only":
        return run_rule_only(incident)

    include_camera = arm != "B_net_only"
    apply_gate = arm == "D_net_cam_gate"
    rule = run_rule_only(incident)
    ms = run_multi_step_investigation(
        incident,
        mode=mode,
        include_camera=include_camera,
        apply_gate=apply_gate,
        demo_mode=demo_mode,
        allow_containment_in_demo=allow_containment_in_demo,
        rule_fusion=rule.fusion if apply_gate else None,
    )

    path_name = {
        "B_net_only": "nemotron_net_only",
        "C_net_cam": "nemotron_net_cam",
        "D_net_cam_gate": "nemotron_net_cam_gate",
    }[arm]

    if not ms.ok or ms.fusion_for_policy is None:
        return PathResult(
            path=path_name,
            recommended_action=None,
            policy_status=None,
            ok=False,
            evidence_class=ms.evidence_class,
            gated_notes=list(ms.gated_notes),
            latency_ms=ms.latency_ms,
            usage=dict(ms.usage or {}),
            estimated_cost_usd=ms.estimated_cost_usd,
            error=ms.error,
            fusion={
                "trace": [t.to_dict() for t in ms.trace],
                "tool_calls": ms.tool_calls,
                "model_calls": ms.model_calls,
                "bundle": ms.bundle,
                "conclusion_kind": ms.conclusion_kind,
                "pre_gate_action": ms.pre_gate_action,
                "pre_gate_source": ms.pre_gate_source,
            },
        )

    net = str(incident.get("network_prediction") or "Normal")
    status, n_rules = _policy_apply(
        net,
        str(incident.get("dpid") or "1"),
        str(incident.get("src_ip") or "10.0.0.15"),
        ms.fusion_for_policy,
    )
    rec = ms.recommendation
    return PathResult(
        path=path_name,
        recommended_action=rec.recommended_action if rec else None,
        policy_status=status,
        applied_rules_count=n_rules,
        final_risk=rec.final_risk if rec else None,
        rationale=rec.rationale if rec else None,
        evidence_class=ms.evidence_class,
        gated_notes=list(ms.gated_notes),
        latency_ms=ms.latency_ms,
        usage=dict(ms.usage or {}),
        estimated_cost_usd=ms.estimated_cost_usd,
        ok=True,
        fusion={
            **(ms.fusion_for_policy or {}),
            "trace": [t.to_dict() for t in ms.trace],
            "tool_calls": ms.tool_calls,
            "model_calls": ms.model_calls,
            "include_camera": include_camera,
            "apply_gate": apply_gate,
            "planner": ms.planner,
            "conclusion_kind": ms.conclusion_kind,
            "pre_gate_action": ms.pre_gate_action,
            "pre_gate_source": ms.pre_gate_source,
            "pre_gate_recommendation": ms.pre_gate_recommendation,
        },
    )


def evidence_request_useful(path: PathResult, oracle: dict[str, Any]) -> bool:
    """True if tools/escalation helped abstain when oracle prefers abstention."""
    fus = path.fusion or {}
    tool_calls = int(fus.get("tool_calls") or 0)
    notes = list(path.gated_notes or [])
    prefer = bool(oracle.get("prefer_abstention") or oracle.get("forbid_containment"))
    if not prefer:
        return bool(tool_calls > 0 and path.ok)
    abstained = path.recommended_action == "observe" or not path.ok
    evidence_gate = any("evidence_insufficient" in n for n in notes)
    return bool(tool_calls > 0 and abstained and (evidence_gate or path.recommended_action == "observe"))
