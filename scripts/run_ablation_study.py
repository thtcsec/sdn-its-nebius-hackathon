#!/usr/bin/env python3
"""Fair ablation on identical held-out inputs (A/B/C/D).

A rule_only | B net-only multi-step | C net+cam (no gate) | D net+cam+gate

Offline arms use deterministic planner + real tools (NOT live Nemotron).
Live Nebius only when --real-limit > 0 and budget allows; never fabricate accuracy.
Default additional budget cap: USD 0.10.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from sdn_its.llm.ablation import Arm, evidence_request_useful, run_ablation_arm  # noqa: E402
from sdn_its.llm.eval_metrics import score_path_vs_oracle  # noqa: E402
from sdn_its.llm.eval_set import assert_disjoint_from_dev, load_eval_cases, select_real_api_subset  # noqa: E402
from sdn_its.utils.env import ensure_repo_env, nebius_config_summary  # noqa: E402

ARMS: list[Arm] = ["A_rule_only", "B_net_only", "C_net_cam", "D_net_cam_gate"]


def _agg(rows: list[dict], arm: str) -> dict:
    scored = [r for r in rows if not r["arms"][arm].get("skipped")]
    n = len(scored) or 1
    keys = [
        "correct_vs_oracle",
        "false_escalation",
        "unsafe_recommendation",
        "abstention",
        "appropriate_abstention",
        "gate_blocked_containment",
        "evidence_request_useful",
    ]
    out: dict = {"n": len(scored), "arm": arm}
    for k in keys:
        vals = [bool(r["arms"][arm]["oracle_score"].get(k)) for r in scored]
        out[f"{k}_rate"] = sum(vals) / n
        out[f"{k}_count"] = sum(vals)
    lats = [r["arms"][arm].get("latency_ms") for r in scored]
    lats_f = [float(x) for x in lats if isinstance(x, (int, float))]
    out["mean_latency_ms"] = sum(lats_f) / len(lats_f) if lats_f else None
    costs = [r["arms"][arm].get("estimated_cost_usd") for r in scored]
    costs_f = [float(x) for x in costs if isinstance(x, (int, float))]
    out["total_estimated_cost_usd"] = sum(costs_f) if costs_f else 0.0
    tools = [int(r["arms"][arm].get("tool_calls") or 0) for r in scored]
    out["mean_tool_calls"] = sum(tools) / n
    tokens = [int((r["arms"][arm].get("usage") or {}).get("total_tokens") or 0) for r in scored]
    out["total_tokens"] = sum(tokens)
    out["evidence_classes"] = sorted(
        {r["arms"][arm].get("evidence_class") for r in scored if r["arms"][arm].get("evidence_class")}
    )
    return out


def main() -> int:
    ensure_repo_env()
    parser = argparse.ArgumentParser(description="Held-out ablation A/B/C/D")
    parser.add_argument("--real-limit", type=int, default=0, help="Max cases with live Nebius for B/C/D")
    parser.add_argument("--budget-usd", type=float, default=0.10, help="Hard stop for estimated USD")
    parser.add_argument("--skip-real", action="store_true", help="Force offline planner for B/C/D")
    parser.add_argument("--demo-mode", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--allow-containment-in-demo", action="store_true", default=False)
    parser.add_argument(
        "--out",
        default=str(ROOT / "artifacts" / "hackathon" / "ablation_last.json"),
    )
    args = parser.parse_args()

    if args.budget_usd > 0.10 + 1e-9:
        print("ERROR: budget-usd must be <= 0.10 for this competition pass", file=sys.stderr)
        return 2

    cases = load_eval_cases()
    assert_disjoint_from_dev(cases)
    real_ids: set[str] = set()
    if not args.skip_real and args.real_limit > 0:
        real_ids = {c["id"] for c in select_real_api_subset(cases, limit=args.real_limit, budget_usd=args.budget_usd)}

    rows: list[dict] = []
    spent = 0.0
    real_calls = 0
    budget_stopped = False

    for case in cases:
        oracle = dict(case.get("oracle") or {})
        force = case.get("force_mode")
        arm_blocks: dict[str, Any] = {}

        for arm in ARMS:
            use_real = (
                arm != "A_rule_only"
                and case["id"] in real_ids
                and not args.skip_real
                and not budget_stopped
                and spent < args.budget_usd
                and not force
            )
            mode = "real" if use_real else "offline"

            # Protocol probes always offline declared modes
            if force in {"malformed_synthetic", "unavailable_api", "synthetic_json"}:
                mode = "offline"

            if arm != "A_rule_only" and mode == "offline" and force not in {
                "malformed_synthetic",
                "unavailable_api",
                "synthetic_json",
            }:
                # Offline multi-step uses deterministic planner (labeled) — always runnable
                path = run_ablation_arm(
                    case,
                    arm,
                    mode="offline",
                    demo_mode=args.demo_mode,
                    allow_containment_in_demo=args.allow_containment_in_demo,
                )
            elif arm == "A_rule_only":
                path = run_ablation_arm(case, arm, mode="offline")
            else:
                path = run_ablation_arm(
                    case,
                    arm,
                    mode=mode,  # type: ignore[arg-type]
                    demo_mode=args.demo_mode,
                    allow_containment_in_demo=args.allow_containment_in_demo,
                )

            score = score_path_vs_oracle(
                path.recommended_action,
                path.ok,
                oracle,
                gated_notes=path.gated_notes,
            )
            score["evidence_request_useful"] = evidence_request_useful(path, oracle)
            fus = path.fusion if isinstance(path.fusion, dict) else {}
            cost = float(path.estimated_cost_usd or 0.0)
            if path.evidence_class == "real_api" and cost:
                spent += cost
                real_calls += 1
                if spent >= args.budget_usd:
                    budget_stopped = True
                    print(f"budget reached ~${spent:.6f}; stopping further real calls", file=sys.stderr)

            arm_blocks[arm] = {
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
                "oracle_score": score,
                "skipped": False,
                "error": path.error,
            }

        rows.append(
            {
                "incident_id": case["id"],
                "family": case.get("family"),
                "oracle": oracle,
                "arms": arm_blocks,
            }
        )

    summary = {arm: _agg(rows, arm) for arm in ARMS}
    report = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "study": "ablation_A_B_C_D",
        "split": "heldout_eval",
        "n_cases": len(rows),
        "of_backend": "mock",
        "demo_mode": args.demo_mode,
        "allow_containment_in_demo": args.allow_containment_in_demo,
        "real_api": {
            "calls": real_calls,
            "est_cost_usd": spent,
            "budget_usd": args.budget_usd,
            "limit": args.real_limit,
            "skipped": args.skip_real or args.real_limit <= 0,
            "budget_stopped": budget_stopped,
            "config": nebius_config_summary() if real_calls else None,
        },
        "arms": {
            "A_rule_only": "Deterministic FusionEngine + PolicyEngine",
            "B_net_only": "Multi-step investigation, network telemetry only (+gate)",
            "C_net_cam": "Multi-step network + camera metadata, schema only (gate skipped)",
            "D_net_cam_gate": "Multi-step network + camera + deterministic safety gate",
        },
        "summary": summary,
        "honesty_note": (
            "Offline B/C/D use deterministic_planner + real evidence tools — NOT live Nemotron. "
            "real_api rows are the only live NVIDIA/Nebius decisions. "
            "Do not claim superiority over rules unless comparable n and evidence_class support it. "
            "Camera fields are fixture/synthetic metadata, not live RTSP inference."
        ),
        "cases": rows,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    # Tracked offline snapshot
    if args.skip_real or args.real_limit <= 0:
        tracked = ROOT / "artifacts" / "hackathon" / "ablation_offline.json"
        tracked.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(f"wrote {tracked}")

    print(
        json.dumps(
            {
                "n_cases": len(rows),
                "summary_correct": {a: summary[a].get("correct_vs_oracle_rate") for a in ARMS},
                "summary_false_escalation": {a: summary[a].get("false_escalation_rate") for a in ARMS},
                "real_api_cost_usd": spent,
                "out": str(out),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
