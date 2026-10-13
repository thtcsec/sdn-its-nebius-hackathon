#!/usr/bin/env python3
"""Final paired study: camera B vs C (live) + causal gate replay (no second Nemotron).

Budget hard-cap: USD 0.10 additional.
Adversarial gate tests are synthetic and excluded from live accuracy.
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
from sdn_its.llm.eval_set import assert_disjoint_from_dev, load_eval_cases  # noqa: E402
from sdn_its.llm.multi_step import run_multi_step_investigation  # noqa: E402
from sdn_its.llm.paired_gate import adversarial_gate_cases, replay_recommendation_pair  # noqa: E402
from sdn_its.utils.env import ensure_repo_env, nebius_config_summary  # noqa: E402

MATCHED_IDS = [
    "eval_legit_cong_01",
    "eval_suspicious_01",
    "eval_missing_01",
    "eval_conflict_01",
]
CONTAINMENT = frozenset({"rate_limit", "temporary_drop"})


def _miss_threat(action: str | None, ok: bool, oracle: dict[str, Any], family: str) -> bool:
    if family != "suspicious_traffic":
        return False
    allowed = set(oracle.get("allowed_actions") or [])
    wants = bool(allowed & CONTAINMENT) and not oracle.get("forbid_containment")
    if not wants:
        return False
    return bool(ok and action == "observe") or (not ok)


def _tools(trace: list[dict[str, Any]]) -> list[str]:
    out = []
    for t in trace:
        if t.get("phase") == "select_evidence_tool" and (t.get("detail") or {}).get("tool"):
            out.append(t["detail"]["tool"])
    return out


def main() -> int:
    ensure_repo_env()
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget-usd", type=float, default=0.10)
    parser.add_argument("--allow-containment-in-demo", action="store_true", default=True)
    parser.add_argument(
        "--out",
        default=str(ROOT / "artifacts" / "hackathon" / "paired_gate_study.json"),
    )
    args = parser.parse_args()
    if args.budget_usd > 0.10 + 1e-9:
        print("ERROR: budget must be <= 0.10", file=sys.stderr)
        return 2

    by_id = {c["id"]: c for c in load_eval_cases()}
    assert_disjoint_from_dev(list(by_id.values()))
    cases = [by_id[i] for i in MATCHED_IDS]

    spent = 0.0
    rows: list[dict[str, Any]] = []

    for case in cases:
        if spent >= args.budget_usd:
            print("budget stop before case", case["id"], file=sys.stderr)
            break
        oracle = dict(case.get("oracle") or {})
        family = str(case.get("family"))
        rule = run_rule_only(case)

        # --- Live B: network only (camera contribution baseline) ---
        b = run_multi_step_investigation(
            case,
            mode="real",
            include_camera=False,
            apply_gate=True,
            demo_mode=True,
            allow_containment_in_demo=args.allow_containment_in_demo,
            rule_fusion=rule.fusion,
        )
        spent += float(b.estimated_cost_usd or 0.0)
        if spent >= args.budget_usd:
            print(f"budget reached ~${spent:.6f} after B {case['id']}", file=sys.stderr)

        # --- Live C capture: network+camera, gate OFF (freeze pre-gate advisory) ---
        c = run_multi_step_investigation(
            case,
            mode="real",
            include_camera=True,
            apply_gate=False,
            demo_mode=True,
            allow_containment_in_demo=args.allow_containment_in_demo,
            rule_fusion=None,
        )
        spent += float(c.estimated_cost_usd or 0.0)
        if spent >= args.budget_usd:
            print(f"budget reached ~${spent:.6f} after C {case['id']}", file=sys.stderr)

        pre = c.pre_gate_recommendation or (c.recommendation.to_dict() if c.recommendation else None)
        evidence_state = {
            "physical_sufficient": (c.bundle or {}).get("physical_sufficient"),
            "human_escalation_requested": (c.bundle or {}).get("human_escalation_requested"),
            "include_camera": True,
        }

        paired = None
        if pre:
            paired = replay_recommendation_pair(
                pre,
                rule_fusion=rule.fusion,
                evidence_state=evidence_state,
                demo_mode=True,
                allow_containment_in_demo=args.allow_containment_in_demo,
                oracle=oracle,
                family=family,
            )

        b_action = b.recommendation.recommended_action if b.recommendation else None
        c_action = pre.get("recommended_action") if pre else None
        d_action = paired["gated"]["action"] if paired else None

        b_score = score_path_vs_oracle(b_action, b.ok, oracle, gated_notes=b.gated_notes)
        c_score = score_path_vs_oracle(c_action, bool(pre), oracle) if pre else {}
        d_score = paired["gated"]["oracle_score"] if paired else {}

        for sc, act, fam in (
            (b_score, b_action, family),
            (c_score, c_action, family),
            (d_score, d_action, family),
        ):
            if sc:
                sc["miss_threat"] = _miss_threat(act, True, oracle, fam)
                sc["unjustified_containment"] = bool(
                    act in CONTAINMENT and (oracle.get("forbid_containment") or oracle.get("prefer_abstention"))
                )
                sc["appropriate_abstention"] = bool(
                    oracle.get("prefer_abstention") and act == "observe"
                )

        rows.append(
            {
                "incident_id": case["id"],
                "family": family,
                "title": case.get("title"),
                "network_prediction": case.get("network_prediction"),
                "camera_context_source": (case.get("camera") or {}).get("context_source"),
                "oracle": oracle,
                "rule_action": rule.recommended_action,
                "B_net_only": {
                    "ok": b.ok,
                    "action": b_action,
                    "evidence_class": b.evidence_class,
                    "conclusion_kind": b.conclusion_kind,
                    "pre_gate_source": b.pre_gate_source,
                    "tool_calls": b.tool_calls,
                    "model_calls": b.model_calls,
                    "tools": _tools([t.to_dict() for t in b.trace]),
                    "latency_ms": b.latency_ms,
                    "estimated_cost_usd": b.estimated_cost_usd,
                    "usage": b.usage,
                    "oracle_score": b_score,
                    "trace": [t.to_dict() for t in b.trace],
                },
                "C_net_cam_pre_gate": {
                    "ok": c.ok,
                    "action": c_action,
                    "evidence_class": c.evidence_class,
                    "conclusion_kind": c.conclusion_kind,
                    "pre_gate_source": c.pre_gate_source,
                    "tool_calls": c.tool_calls,
                    "model_calls": c.model_calls,
                    "tools": _tools([t.to_dict() for t in c.trace]),
                    "latency_ms": c.latency_ms,
                    "estimated_cost_usd": c.estimated_cost_usd,
                    "usage": c.usage,
                    "oracle_score": c_score,
                    "pre_gate_recommendation": pre,
                    "evidence_bundle": c.bundle,
                    "trace": [t.to_dict() for t in c.trace],
                    "note": "Single live Nemotron capture; gate NOT applied in this call",
                },
                "paired_gate_replay": paired,
                "D_gated_replay_action": d_action,
                "D_oracle_score": d_score,
                "causal_note": (
                    "D is a deterministic replay of C's frozen pre-gate recommendation; "
                    "Nemotron was not called again between ungated and gated variants."
                ),
            }
        )

    # Adversarial (synthetic) — not live accuracy
    adv_results = []
    for adv in adversarial_gate_cases():
        pair = replay_recommendation_pair(
            adv["pre_gate"],
            rule_fusion=adv.get("rule_fusion"),
            evidence_state=adv.get("evidence_state"),
            demo_mode=False,
            allow_containment_in_demo=True,
            oracle=adv.get("oracle"),
            family="adversarial_synthetic",
        )
        ok = True
        if adv.get("expect_change") and not pair["action_changed"]:
            ok = False
        if adv.get("expect_gated_action") and pair["gated"]["action"] != adv["expect_gated_action"]:
            ok = False
        if adv.get("expect_gated_not_in") and pair["gated"]["action"] in set(adv["expect_gated_not_in"]):
            ok = False
        adv_results.append({"id": adv["id"], "title": adv["title"], "pair": pair, "enforcement_ok": ok})

    def _rate(rows_local: list[dict], key_path: str, field: str) -> float | None:
        vals = []
        for r in rows_local:
            cur: Any = r
            for p in key_path.split("."):
                cur = (cur or {}).get(p) if isinstance(cur, dict) else None
            if isinstance(cur, dict) and field in cur:
                vals.append(bool(cur[field]))
        if not vals:
            return None
        return sum(vals) / len(vals)

    n = len(rows) or 1
    summary = {
        "n_cases": len(rows),
        "spent_usd": spent,
        "budget_usd": args.budget_usd,
        "B_correct": _rate(rows, "B_net_only.oracle_score", "correct_vs_oracle"),
        "C_ungated_correct": _rate(rows, "C_net_cam_pre_gate.oracle_score", "correct_vs_oracle"),
        "D_gated_replay_correct": _rate(rows, "D_oracle_score", "correct_vs_oracle"),
        "B_unjustified_containment": _rate(rows, "B_net_only.oracle_score", "unjustified_containment"),
        "C_unjustified_containment": _rate(rows, "C_net_cam_pre_gate.oracle_score", "unjustified_containment"),
        "D_unjustified_containment": _rate(rows, "D_oracle_score", "unjustified_containment"),
        "B_miss_threat": _rate(rows, "B_net_only.oracle_score", "miss_threat"),
        "C_miss_threat": _rate(rows, "C_net_cam_pre_gate.oracle_score", "miss_threat"),
        "D_miss_threat": _rate(rows, "D_oracle_score", "miss_threat"),
        "B_appropriate_abstention": _rate(rows, "B_net_only.oracle_score", "appropriate_abstention"),
        "C_appropriate_abstention": _rate(rows, "C_net_cam_pre_gate.oracle_score", "appropriate_abstention"),
        "D_appropriate_abstention": _rate(rows, "D_oracle_score", "appropriate_abstention"),
        "paired_override_frequency": sum(1 for r in rows if (r.get("paired_gate_replay") or {}).get("action_changed")) / n,
        "paired_override_justified_rate": (
            sum(
                1
                for r in rows
                if (r.get("paired_gate_replay") or {}).get("action_changed")
                and (r.get("paired_gate_replay") or {}).get("override_justified_vs_oracle")
            )
            / max(1, sum(1 for r in rows if (r.get("paired_gate_replay") or {}).get("action_changed")))
        ),
        "C_pre_gate_nemotron_rate": sum(
            1 for r in rows if r.get("C_net_cam_pre_gate", {}).get("pre_gate_source") == "nemotron_conclude"
        )
        / n,
        "C_fallback_rate": sum(
            1 for r in rows if r.get("C_net_cam_pre_gate", {}).get("pre_gate_source") == "deterministic_fallback"
        )
        / n,
        "B_mean_latency_ms": sum(float(r["B_net_only"].get("latency_ms") or 0) for r in rows) / n,
        "C_mean_latency_ms": sum(float(r["C_net_cam_pre_gate"].get("latency_ms") or 0) for r in rows) / n,
        "adversarial_enforcement_pass": all(a["enforcement_ok"] for a in adv_results),
        "adversarial_n": len(adv_results),
    }

    report = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "study": "paired_gate_causal_v1",
        "narrative": (
            "A traffic surge is not always an attack. Before disrupting a cyber-physical system, "
            "investigate the evidence."
        ),
        "intended_user": "ITS network operator / SOC analyst",
        "matched_case_ids": MATCHED_IDS,
        "of_backend": "mock",
        "camera_label": "synthetic_metadata_only",
        "real_api": {
            "est_cost_usd": spent,
            "budget_usd": args.budget_usd,
            "config": {
                "nebius_api_key_present": bool((nebius_config_summary() or {}).get("nebius_api_key_present")),
                "nebius_model": (nebius_config_summary() or {}).get("nebius_model"),
            },
        },
        "methods": {
            "B": "Live Nemotron multi-step, network tools only + gate",
            "C": "Live Nemotron multi-step, network+camera, gate OFF — freezes pre_gate_recommendation",
            "D": "Deterministic replay of C's frozen recommendation through safety gate (no Nemotron recall)",
            "adversarial": "Synthetic forced recommendations — prove gate enforcement, not live accuracy",
        },
        "honesty": (
            "Offline deterministic planner scores are excluded. "
            "C→D differences are causally attributable to the gate only when action_changed on the frozen advisory. "
            "B vs C remain separate live inferences for camera-context contribution."
        ),
        "summary": summary,
        "cases": rows,
        "adversarial_gate_tests": adv_results,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"summary": summary, "out": str(out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
