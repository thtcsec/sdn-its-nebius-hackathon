#!/usr/bin/env python3
"""Held-out evaluation: rule-only vs Nemotron on identical inputs vs oracle labels.

Default: full set rule-only + protocol probes; Nemotron live only on a budgeted subset.
Never fabricates Nebius completions for accuracy. Dev fixtures are excluded.
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

from sdn_its.llm.agent import investigate_case, run_rule_only  # noqa: E402
from sdn_its.llm.eval_metrics import aggregate_oracle_scores, score_path_vs_oracle  # noqa: E402
from sdn_its.llm.eval_set import assert_disjoint_from_dev, load_eval_cases, select_real_api_subset  # noqa: E402
from sdn_its.utils.env import ensure_repo_env, nebius_config_summary  # noqa: E402


def main() -> int:
    ensure_repo_env()
    parser = argparse.ArgumentParser(description="Held-out oracle evaluation")
    parser.add_argument("--real-limit", type=int, default=5, help="Max live Nebius cases")
    parser.add_argument("--budget-usd", type=float, default=0.05, help="Stop real calls after this est. USD")
    parser.add_argument("--skip-real", action="store_true", help="Rule-only + protocol only")
    parser.add_argument("--demo-mode", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--allow-containment-in-demo",
        action="store_true",
        default=False,
        help="For live advisory scoring allow containment intentions (OF still mock)",
    )
    parser.add_argument(
        "--out",
        default=str(ROOT / "artifacts" / "hackathon" / "heldout_eval_last.json"),
    )
    args = parser.parse_args()

    cases = load_eval_cases()
    if len(cases) < 10:
        print("ERROR: held-out set missing — run scripts/generate_heldout_eval.py", file=sys.stderr)
        return 1
    assert_disjoint_from_dev(cases)

    real_ids = set()
    if not args.skip_real:
        real_ids = {c["id"] for c in select_real_api_subset(cases, limit=args.real_limit, budget_usd=args.budget_usd)}

    rows: list[dict] = []
    spent = 0.0
    real_calls = 0

    for case in cases:
        oracle = dict(case.get("oracle") or {})
        force = case.get("force_mode")

        # Always score rule-only on identical inputs
        rule = run_rule_only(case)
        rule_score = score_path_vs_oracle(rule.recommended_action, rule.ok, oracle)

        nemotron_block: dict
        path_result = None

        if force in {"malformed_synthetic", "unavailable_api", "synthetic_json"}:
            # Protocol probes (declared) — not accuracy evidence
            full = investigate_case(
                case,
                mode="offline",
                demo_mode=args.demo_mode,
                allow_containment_in_demo=args.allow_containment_in_demo,
                record=False,
            )
            path_result = full.nemotron
            nemotron_block = path_result.to_dict()
            n_score = score_path_vs_oracle(
                path_result.recommended_action,
                path_result.ok,
                oracle,
                gated_notes=path_result.gated_notes,
            )
            if oracle.get("expect_nemotron_fail_closed"):
                n_score["protocol_fail_closed_ok"] = path_result.ok is False
            if oracle.get("expect_nemotron_api_blocked"):
                n_score["protocol_api_blocked_ok"] = path_result.evidence_class == "blocked_no_credentials"
            if oracle.get("expect_gate_blocks_containment"):
                n_score["protocol_gate_ok"] = path_result.recommended_action not in {"rate_limit", "temporary_drop"}
            evidence = path_result.evidence_class
        elif case["id"] in real_ids and spent < args.budget_usd:
            full = investigate_case(
                case,
                mode="real",
                demo_mode=args.demo_mode,
                allow_containment_in_demo=args.allow_containment_in_demo,
                record=False,
            )
            path_result = full.nemotron
            nemotron_block = path_result.to_dict()
            n_score = score_path_vs_oracle(
                path_result.recommended_action,
                path_result.ok,
                oracle,
                gated_notes=path_result.gated_notes,
            )
            cost = float(path_result.estimated_cost_usd or 0.0)
            spent += cost
            real_calls += 1
            evidence = path_result.evidence_class
            if spent >= args.budget_usd:
                print(f"budget reached ~${spent:.6f} after {real_calls} real calls", file=sys.stderr)
        else:
            nemotron_block = {
                "path": "nemotron_assisted",
                "ok": False,
                "evidence_class": "skipped_no_fake_offline",
                "recommended_action": None,
                "error": "Held-out offline: Nemotron not invented; use --real-limit for live subset.",
            }
            n_score = {
                "action": None,
                "ok": False,
                "correct_vs_oracle": False,
                "false_escalation": False,
                "unsafe_recommendation": False,
                "abstention": True,
                "appropriate_abstention": False,
                "gate_blocked_containment": False,
                "skipped": True,
            }
            evidence = "skipped_no_fake_offline"

        row = {
            "incident_id": case["id"],
            "family": case.get("family"),
            "network_prediction": case.get("network_prediction"),
            "oracle": oracle,
            "rule": rule.to_dict(),
            "nemotron": nemotron_block,
            "oracle_scores": {"rule": rule_score, "nemotron": n_score},
            "metrics": {
                "rule_latency_ms": rule.latency_ms,
                "nemotron_latency_ms": (path_result.latency_ms if path_result else None),
                "estimated_cost_usd": (path_result.estimated_cost_usd if path_result else None),
                "nemotron_evidence_class": evidence,
            },
            "inputs_fingerprint": {
                "telemetry": case.get("telemetry"),
                "camera": case.get("camera"),
            },
        }
        rows.append(row)

    # Aggregates
    rule_agg = aggregate_oracle_scores(rows, "rule")
    # Nemotron aggregates only over scored (non-skipped) rows
    scored = [r for r in rows if not (r.get("oracle_scores", {}).get("nemotron", {}) or {}).get("skipped")]
    real_scored = [
        r
        for r in scored
        if (r.get("nemotron") or {}).get("evidence_class") == "real_api"
    ]
    protocol = [
        r
        for r in scored
        if (r.get("nemotron") or {}).get("evidence_class")
        in {"synthetic_malformed", "blocked_no_credentials", "synthetic_offline", "validation_error"}
        or r.get("family") in {"malformed_output", "api_outage", "unsafe_escalation"}
    ]

    report = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
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
            "skipped": args.skip_real,
            "config": nebius_config_summary() if real_calls else None,
        },
        "summary": {
            "rule_vs_oracle": rule_agg,
            "nemotron_real_api_vs_oracle": aggregate_oracle_scores(real_scored, "nemotron") if real_scored else {"n": 0},
            "nemotron_protocol_probes": aggregate_oracle_scores(protocol, "nemotron") if protocol else {"n": 0},
            "dev_fixtures_excluded": True,
            "honesty_note": (
                "Dev fixtures under incidents/ are regression-only and excluded. "
                "Held-out Nemotron accuracy uses only real_api rows (or declared protocol probes). "
                "skipped_no_fake_offline rows are not scored as model accuracy."
            ),
        },
        "cases": rows,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    # Tracked snapshot when skip-real (fully reproducible, $0)
    if args.skip_real:
        tracked = ROOT / "artifacts" / "hackathon" / "heldout_eval_rule_only.json"
        tracked.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(f"wrote {tracked}")

    print(
        json.dumps(
            {
                "n_cases": report["n_cases"],
                "rule_correct_rate": rule_agg.get("correct_vs_oracle_rate"),
                "rule_false_escalation_rate": rule_agg.get("false_escalation_rate"),
                "real_api_n": len(real_scored),
                "real_api_cost_usd": spent,
                "out": str(out),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
