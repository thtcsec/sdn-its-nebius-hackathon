#!/usr/bin/env python3
"""Matched live Nemotron proof: same 4 cases × arms A/B/C/D within USD 0.10.

Preselected families (held-out, not tuned on):
  - legitimate_congestion  (legit surge)
  - suspicious_traffic     (plausible attack)
  - missing_evidence       (stale/missing camera)
  - contradictory_evidence (conflict)

B/C/D require evidence_class=real_api and Nemotron-chosen tool_calls.
Offline 92% planner scores are NOT reported here.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from sdn_its.llm.ablation import Arm, evidence_request_useful, run_ablation_arm  # noqa: E402
from sdn_its.llm.eval_metrics import score_path_vs_oracle  # noqa: E402
from sdn_its.llm.eval_set import assert_disjoint_from_dev, load_eval_cases  # noqa: E402
from sdn_its.utils.env import ensure_repo_env, nebius_config_summary  # noqa: E402

MATCHED_IDS = [
    "eval_legit_cong_01",
    "eval_suspicious_01",
    "eval_missing_01",
    "eval_conflict_01",
]
ARMS: list[Arm] = ["A_rule_only", "B_net_only", "C_net_cam", "D_net_cam_gate"]
CONTAINMENT = frozenset({"rate_limit", "temporary_drop"})


def _miss_threat(action: str | None, ok: bool, oracle: dict[str, Any], family: str) -> bool:
    """True if oracle expects containment/response to attack-like case but path only observes/fails."""
    if family not in {"suspicious_traffic"}:
        return False
    allowed = set(oracle.get("allowed_actions") or [])
    wants_contain = bool(allowed & CONTAINMENT) and not oracle.get("forbid_containment")
    if not wants_contain:
        return False
    return bool(ok and action == "observe") or (not ok)


def _unjustified_containment(action: str | None, ok: bool, oracle: dict[str, Any]) -> bool:
    return bool(ok and action in CONTAINMENT and (oracle.get("forbid_containment") or oracle.get("prefer_abstention")))


def _trace_tools(path_fusion: dict[str, Any] | None) -> list[dict[str, Any]]:
    fus = path_fusion or {}
    out = []
    for step in fus.get("trace") or []:
        phase = step.get("phase")
        detail = step.get("detail") or {}
        if phase in {
            "select_evidence_tool",
            "retrieve_validate",
            "reason",
            "policy_gate",
            "detect",
            "identify_uncertainty",
            "final_reason_prompt",
            "audit",
        }:
            out.append({"phase": phase, "detail": detail})
    return out


def _nemotron_chose_tools(fus: dict[str, Any] | None) -> bool:
    """True if at least one tool was selected without forced_after_premature_conclude auto-exec."""
    for step in (fus or {}).get("trace") or []:
        if step.get("phase") != "select_evidence_tool":
            continue
        d = step.get("detail") or {}
        if d.get("tool") and not d.get("forced_after_premature_conclude"):
            if d.get("rejected_premature_conclude"):
                continue
            return True
    return int((fus or {}).get("tool_calls") or 0) > 0


def main() -> int:
    ensure_repo_env()
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget-usd", type=float, default=0.10)
    parser.add_argument("--allow-containment-in-demo", action="store_true", default=True)
    parser.add_argument(
        "--out",
        default=str(ROOT / "artifacts" / "hackathon" / "matched_nemotron_proof.json"),
    )
    args = parser.parse_args()
    if args.budget_usd > 0.10 + 1e-9:
        print("ERROR: budget must be <= 0.10", file=sys.stderr)
        return 2

    all_cases = {c["id"]: c for c in load_eval_cases()}
    assert_disjoint_from_dev(list(all_cases.values()))
    cases = []
    for cid in MATCHED_IDS:
        if cid not in all_cases:
            print(f"ERROR: missing case {cid}", file=sys.stderr)
            return 1
        cases.append(all_cases[cid])

    spent = 0.0
    budget_stopped = False
    rows: list[dict[str, Any]] = []

    for case in cases:
        if budget_stopped:
            break
        oracle = dict(case.get("oracle") or {})
        family = str(case.get("family"))
        arm_blocks: dict[str, Any] = {}

        for arm in ARMS:
            if arm != "A_rule_only" and spent >= args.budget_usd:
                budget_stopped = True
                arm_blocks[arm] = {
                    "skipped": True,
                    "evidence_class": "skipped_budget",
                    "error": f"budget reached ${spent:.6f}",
                }
                continue

            mode = "offline" if arm == "A_rule_only" else "real"
            path = run_ablation_arm(
                case,
                arm,
                mode=mode,  # type: ignore[arg-type]
                demo_mode=True,
                allow_containment_in_demo=bool(args.allow_containment_in_demo),
            )
            fus = path.fusion if isinstance(path.fusion, dict) else {}
            score = score_path_vs_oracle(
                path.recommended_action,
                path.ok,
                oracle,
                gated_notes=path.gated_notes,
            )
            score["evidence_request_useful"] = evidence_request_useful(path, oracle)
            score["unjustified_containment"] = _unjustified_containment(
                path.recommended_action, path.ok, oracle
            )
            score["miss_threat"] = _miss_threat(path.recommended_action, path.ok, oracle, family)

            cost = float(path.estimated_cost_usd or 0.0)
            if path.evidence_class == "real_api":
                spent += cost
                if spent >= args.budget_usd:
                    budget_stopped = True
                    print(f"budget reached ~${spent:.6f}", file=sys.stderr)

            arm_blocks[arm] = {
                "skipped": False,
                "action": path.recommended_action,
                "ok": path.ok,
                "evidence_class": path.evidence_class,
                "gated_notes": path.gated_notes,
                "latency_ms": path.latency_ms,
                "estimated_cost_usd": path.estimated_cost_usd,
                "usage": path.usage,
                "tool_calls": fus.get("tool_calls"),
                "model_calls": fus.get("model_calls"),
                "planner": fus.get("planner"),
                "model": None,
                "nemotron_chose_tools": _nemotron_chose_tools(fus) if arm != "A_rule_only" else None,
                "conclusion_kind": fus.get("conclusion_kind"),
                "pre_gate_action": fus.get("pre_gate_action"),
                "pre_gate_source": fus.get("pre_gate_source"),
                "oracle_score": score,
                "error": path.error,
                "rationale": path.rationale,
                "trace": _trace_tools(fus),
                "policy_status": path.policy_status,
            }

            # attach model id from nested fusion if present
            for step in fus.get("trace") or []:
                pass

        rows.append(
            {
                "incident_id": case["id"],
                "family": family,
                "title": case.get("title"),
                "network_prediction": case.get("network_prediction"),
                "camera_context_source": (case.get("camera") or {}).get("context_source"),
                "oracle": oracle,
                "arms": arm_blocks,
            }
        )

    def agg(arm: str) -> dict[str, Any]:
        scored = [r for r in rows if not r["arms"].get(arm, {}).get("skipped")]
        n = len(scored) or 1
        keys = [
            "correct_vs_oracle",
            "false_escalation",
            "unjustified_containment",
            "miss_threat",
            "unsafe_recommendation",
            "abstention",
            "appropriate_abstention",
            "evidence_request_useful",
            "gate_blocked_containment",
        ]
        out: dict[str, Any] = {"n": len(scored), "arm": arm}
        for k in keys:
            vals = [bool((r["arms"][arm].get("oracle_score") or {}).get(k)) for r in scored]
            out[f"{k}_rate"] = sum(vals) / n
            out[f"{k}_count"] = sum(vals)
        lats = [r["arms"][arm].get("latency_ms") for r in scored if isinstance(r["arms"][arm].get("latency_ms"), (int, float))]
        out["mean_latency_ms"] = sum(lats) / len(lats) if lats else None
        costs = [float(r["arms"][arm].get("estimated_cost_usd") or 0) for r in scored]
        out["total_estimated_cost_usd"] = sum(costs)
        tools = [int(r["arms"][arm].get("tool_calls") or 0) for r in scored]
        out["mean_tool_calls"] = sum(tools) / n
        tokens = [int((r["arms"][arm].get("usage") or {}).get("total_tokens") or 0) for r in scored]
        out["total_tokens"] = sum(tokens)
        if arm != "A_rule_only":
            chose = [bool(r["arms"][arm].get("nemotron_chose_tools")) for r in scored]
            out["nemotron_chose_tools_rate"] = sum(chose) / n
            out["real_api_n"] = sum(1 for r in scored if r["arms"][arm].get("evidence_class") == "real_api")
            kinds = [str(r["arms"][arm].get("conclusion_kind") or "") for r in scored]
            out["conclusion_kind_counts"] = {
                "nemotron_conclude": kinds.count("nemotron_conclude"),
                "deterministic_fallback": kinds.count("deterministic_fallback"),
                "policy_overridden": kinds.count("policy_overridden"),
            }
            out["nemotron_conclude_rate"] = kinds.count("nemotron_conclude") / n
            out["pre_gate_nemotron_rate"] = (
                sum(1 for r in scored if r["arms"][arm].get("pre_gate_source") == "nemotron_conclude") / n
            )
        out["evidence_classes"] = sorted(
            {r["arms"][arm].get("evidence_class") for r in scored if r["arms"][arm].get("evidence_class")}
        )
        out["actions"] = {r["incident_id"]: r["arms"][arm].get("action") for r in scored}
        out["conclusion_kinds"] = {r["incident_id"]: r["arms"][arm].get("conclusion_kind") for r in scored}
        return out

    report = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "study": "matched_live_nemotron_ABCD",
        "narrative": (
            "A traffic surge is not always an attack. "
            "Before disrupting a cyber-physical system, investigate the evidence."
        ),
        "intended_user": "ITS network operator / SOC analyst deciding whether to contain RSU-edge traffic",
        "matched_case_ids": MATCHED_IDS,
        "n_cases": len(rows),
        "of_backend": "mock",
        "camera_label": "synthetic_metadata_only",
        "budget_usd": args.budget_usd,
        "spent_usd": spent,
        "budget_stopped": budget_stopped,
        "real_api": {
            "est_cost_usd": spent,
            "config": {
                "nebius_api_key_present": bool((nebius_config_summary() or {}).get("nebius_api_key_present")),
                "nebius_base_url_set": bool((nebius_config_summary() or {}).get("nebius_base_url_set")),
                "nebius_model": (nebius_config_summary() or {}).get("nebius_model"),
                "note": "API key never written to artifacts.",
            },
        },
        "arms": {
            "A_rule_only": "Deterministic FusionEngine (no Nebius)",
            "B_net_only": "Live Nemotron multi-step, network tools only + gate",
            "C_net_cam": "Live Nemotron multi-step, network + camera tools, gate skipped",
            "D_net_cam_gate": "Live Nemotron multi-step, network + camera + safety gate",
        },
        "summary": {a: agg(a) for a in ARMS},
        "separation_note": (
            "This report is LIVE Nemotron only for B/C/D. "
            "The offline deterministic-planner 92% figure from ablation_offline.json "
            "must NEVER be advertised as Nemotron accuracy."
        ),
        "cases": rows,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {
                "n_cases": len(rows),
                "spent_usd": spent,
                "summary_correct": {a: report["summary"][a].get("correct_vs_oracle_rate") for a in ARMS},
                "summary_unjustified_containment": {
                    a: report["summary"][a].get("unjustified_containment_rate") for a in ARMS
                },
                "nemotron_tool_choice": {
                    a: report["summary"][a].get("nemotron_chose_tools_rate")
                    for a in ARMS
                    if a != "A_rule_only"
                },
                "nemotron_conclude_rate": {
                    a: report["summary"][a].get("nemotron_conclude_rate")
                    for a in ARMS
                    if a != "A_rule_only"
                },
                "pre_gate_nemotron_rate": {
                    a: report["summary"][a].get("pre_gate_nemotron_rate")
                    for a in ARMS
                    if a != "A_rule_only"
                },
                "conclusion_kind_counts": {
                    a: report["summary"][a].get("conclusion_kind_counts")
                    for a in ARMS
                    if a != "A_rule_only"
                },
                "out": str(out),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
