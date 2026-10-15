#!/usr/bin/env python3
"""Post-fix independent regression (not retuned on blind oracles).

Hard additional Nebius budget: USD 0.10.
Uses a small fixed set: 2 blind stress cases + 2 held-out eval cases.
Reports model contribution, failures, containment risk, fallback, latency separately.
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

from sdn_its.llm.agent import run_rule_only  # noqa: E402
from sdn_its.llm.eval_metrics import score_path_vs_oracle  # noqa: E402
from sdn_its.llm.eval_set import load_eval_cases  # noqa: E402
from sdn_its.llm.multi_step import run_multi_step_investigation  # noqa: E402
from sdn_its.llm.paired_gate import replay_recommendation_pair  # noqa: E402
from sdn_its.utils.env import ensure_repo_env, nebius_config_summary  # noqa: E402

# Independent regression IDs — fixed, not iteratively tuned against this script.
REGRESSION_IDS = [
    "blind_unreliable_telemetry",  # crash fix
    "blind_attack_quiet_road",  # prior "..." conclude failure
    "eval_missing_01",  # held-out stale/missing
    "eval_legit_cong_01",  # held-out legit surge
]
CONTAINMENT = frozenset({"rate_limit", "temporary_drop"})


def load_case(cid: str) -> dict[str, Any]:
    if cid.startswith("blind_"):
        p = ROOT / "datasets" / "hackathon" / "blind" / f"{cid}.json"
        return json.loads(p.read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in load_eval_cases()}
    return by_id[cid]


def main() -> int:
    ensure_repo_env()
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget-usd", type=float, default=0.10)
    parser.add_argument("--skip-real", action="store_true")
    parser.add_argument(
        "--out",
        default=str(ROOT / "artifacts" / "hackathon" / "p0_regression_eval.json"),
    )
    args = parser.parse_args()
    if args.budget_usd > 0.10 + 1e-9:
        print("ERROR: budget must be <= 0.10", file=sys.stderr)
        return 2

    spent = 0.0
    rows = []
    for cid in REGRESSION_IDS:
        case = load_case(cid)
        oracle = dict(case.get("oracle") or {})
        family = str(case.get("family") or "")
        rule = run_rule_only(case)
        b = run_multi_step_investigation(
            case,
            mode="offline",
            include_camera=True,
            apply_gate=True,
            demo_mode=False,
            allow_containment_in_demo=True,
            rule_fusion=rule.fusion,
        )
        b_act = b.recommendation.recommended_action if b.recommendation else None
        row: dict[str, Any] = {
            "incident_id": cid,
            "family": family,
            "A_rules": {
                "action": rule.recommended_action,
                "ok": rule.ok,
                "oracle_score": score_path_vs_oracle(rule.recommended_action, rule.ok, oracle),
            },
            "B_planner": {
                "action": b_act,
                "ok": b.ok,
                "conclusion_kind": b.conclusion_kind,
                "oracle_score": score_path_vs_oracle(b_act, b.ok, oracle, gated_notes=b.gated_notes),
            },
        }
        if args.skip_real or spent >= args.budget_usd:
            row["C_nemotron"] = {"skipped": True}
            row["D_gate_replay"] = {"skipped": True}
        else:
            c = run_multi_step_investigation(
                case,
                mode="real",
                include_camera=True,
                apply_gate=False,
                demo_mode=True,
                allow_containment_in_demo=True,
                rule_fusion=None,
            )
            spent += float(c.estimated_cost_usd or 0.0)
            pre = c.pre_gate_recommendation or (c.recommendation.to_dict() if c.recommendation else None)
            c_act = pre.get("recommended_action") if pre else None
            row["C_nemotron"] = {
                "action": c_act,
                "ok": c.ok,
                "evidence_class": c.evidence_class,
                "conclusion_kind": c.conclusion_kind,
                "pre_gate_source": c.pre_gate_source,
                "tool_calls": c.tool_calls,
                "model_calls": c.model_calls,
                "latency_ms": c.latency_ms,
                "estimated_cost_usd": c.estimated_cost_usd,
                "error": c.error,
                "oracle_score": score_path_vs_oracle(c_act, bool(pre), oracle) if pre else {},
                "trace": [t.to_dict() for t in c.trace],
                "pre_gate_recommendation": pre,
                "containment": c_act in CONTAINMENT if c_act else False,
            }
            if pre:
                pair = replay_recommendation_pair(
                    pre,
                    rule_fusion=rule.fusion,
                    evidence_state={
                        "physical_sufficient": (c.bundle or {}).get("physical_sufficient"),
                        "human_escalation_requested": (c.bundle or {}).get("human_escalation_requested"),
                        "include_camera": True,
                    },
                    demo_mode=True,
                    allow_containment_in_demo=True,
                    oracle=oracle,
                    family=family,
                )
                row["D_gate_replay"] = {
                    "action": pair["gated"]["action"],
                    "action_changed": pair["action_changed"],
                    "oracle_score": pair["gated"]["oracle_score"],
                }
            else:
                row["D_gate_replay"] = {"skipped": True, "reason": "no_valid_pre_gate"}
        rows.append(row)

    def rate(arm: str, field: str) -> float | None:
        vals = []
        for r in rows:
            sc = (r.get(arm) or {}).get("oracle_score") or {}
            if (r.get(arm) or {}).get("skipped"):
                continue
            if field in sc:
                vals.append(bool(sc[field]))
        return (sum(vals) / len(vals)) if vals else None

    c_rows = [r["C_nemotron"] for r in rows if not r.get("C_nemotron", {}).get("skipped")]
    summary = {
        "n": len(rows),
        "spent_usd": spent,
        "budget_usd": args.budget_usd,
        "A_correct": rate("A_rules", "correct_vs_oracle"),
        "B_correct": rate("B_planner", "correct_vs_oracle"),
        "C_correct": rate("C_nemotron", "correct_vs_oracle"),
        "D_correct": rate("D_gate_replay", "correct_vs_oracle"),
        "C_nemotron_conclude_rate": (
            sum(1 for c in c_rows if c.get("pre_gate_source") == "nemotron_conclude") / len(c_rows)
            if c_rows
            else None
        ),
        "C_fallback_rate": (
            sum(1 for c in c_rows if c.get("pre_gate_source") == "deterministic_fallback") / len(c_rows)
            if c_rows
            else None
        ),
        "C_validation_error_rate": (
            sum(1 for c in c_rows if c.get("evidence_class") == "validation_error") / len(c_rows) if c_rows else None
        ),
        "C_containment_rate": (
            sum(1 for c in c_rows if c.get("containment")) / len(c_rows) if c_rows else None
        ),
        "C_mean_latency_ms": (
            sum(float(c.get("latency_ms") or 0) for c in c_rows) / len(c_rows) if c_rows else None
        ),
        "C_mean_tool_calls": (
            sum(int(c.get("tool_calls") or 0) for c in c_rows) / len(c_rows) if c_rows else None
        ),
        "unreliable_no_crash": all(
            (r["A_rules"].get("action") == "observe" and r["B_planner"].get("ok"))
            for r in rows
            if r["incident_id"] == "blind_unreliable_telemetry"
        ),
    }
    report = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "study": "p0_regression_v1",
        "regression_ids": REGRESSION_IDS,
        "honesty": (
            "Fixed ID list chosen for crash/placeholder regressions + two held-out cases. "
            "Oracles not altered. Not claimed as full blind prevalence."
        ),
        "real_api": {
            "nebius_api_key_present": bool((nebius_config_summary() or {}).get("nebius_api_key_present")),
            "nebius_model": (nebius_config_summary() or {}).get("nebius_model"),
            "spent_usd": spent,
        },
        "summary": summary,
        "cases": rows,
        "analysis_prior_blind_gap": {
            "why_planner_beat_nemotron": [
                "blind_attack_quiet_road: Nemotron reserved conclude emitted recommended_action='...' (placeholder) → schema reject; planner used rate_limit from evidence rules.",
                "blind_contradict: Nemotron tools ran (real_api) but final conclude fell to deterministic_fallback — tool selection value without successful model conclude.",
                "Overall: planner encodes explicit physical/gate heuristics; model contribution is tool selection + conclude quality, which was brittle on placeholders.",
            ]
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"summary": summary, "out": str(out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
