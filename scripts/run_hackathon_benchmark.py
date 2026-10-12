#!/usr/bin/env python3
"""Benchmark: deterministic rule-only vs Nemotron-assisted investigation.

Default ``--mode offline`` uses synthetic model outputs in fixtures (reproducible,
no API cost). ``--mode real`` calls Nebius for fixtures without force_mode
(requires repo-root .env). Never prints API keys.
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

from sdn_its.llm.agent import investigate_case  # noqa: E402
from sdn_its.llm.fixtures import load_all_incidents  # noqa: E402
from sdn_its.utils.env import ensure_repo_env, nebius_config_summary  # noqa: E402


def aggregate(rows: list[dict]) -> dict:
    n = len(rows) or 1
    def _mean(key):
        vals = [r["metrics"].get(key) for r in rows if isinstance(r["metrics"].get(key), (int, float))]
        return sum(vals) / len(vals) if vals else None

    agreements = [bool(r["metrics"].get("decision_agreement")) for r in rows]
    inappropriate = [bool(r["metrics"].get("inappropriate_containment")) for r in rows]
    gates = [bool(r["metrics"].get("escalation_or_demo_gate_fired")) for r in rows]
    abstain = [bool(r["metrics"].get("abstention_or_fail_closed")) for r in rows]
    costs = [r["metrics"].get("estimated_cost_usd") for r in rows if r["metrics"].get("estimated_cost_usd") is not None]
    return {
        "n_incidents": len(rows),
        "decision_agreement_rate": sum(agreements) / n,
        "inappropriate_containment_rate": sum(inappropriate) / n,
        "gate_fired_rate": sum(gates) / n,
        "abstention_or_fail_closed_rate": sum(abstain) / n,
        "mean_rule_latency_ms": _mean("rule_latency_ms"),
        "mean_nemotron_latency_ms": _mean("nemotron_latency_ms"),
        "total_estimated_cost_usd": sum(costs) if costs else 0.0,
        "honesty_note": (
            "Agreement measures action match between rule fusion and gated Nemotron path. "
            "It is NOT a claim that Nemotron improves accuracy. Offline mode uses synthetic "
            "model JSON labeled synthetic_offline / synthetic_malformed."
        ),
    }


def main() -> int:
    ensure_repo_env()
    parser = argparse.ArgumentParser(description="Hackathon rule vs Nemotron benchmark")
    parser.add_argument("--mode", choices=("offline", "real"), default="offline")
    parser.add_argument("--demo-mode", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--allow-containment-in-demo",
        action="store_true",
        default=False,
        help="Allow rate_limit/temporary_drop intentions through the demo gate (OF still mock).",
    )
    parser.add_argument(
        "--out",
        default=str(ROOT / "artifacts" / "hackathon" / "benchmark_last.json"),
    )
    args = parser.parse_args()

    incidents = load_all_incidents()
    if len(incidents) < 4:
        print("ERROR: need at least 4 incident fixtures", file=sys.stderr)
        return 1

    rows = []
    for inc in incidents:
        # In real mode, forced scenarios still use their force_mode (malformed / unavailable)
        case = investigate_case(
            inc,
            mode=args.mode,
            demo_mode=args.demo_mode,
            allow_containment_in_demo=args.allow_containment_in_demo,
            record=True,
        )
        rows.append(case.to_dict())

    report = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "demo_mode": args.demo_mode,
        "allow_containment_in_demo": args.allow_containment_in_demo,
        "of_backend_default": "mock",
        "config": nebius_config_summary() if args.mode == "real" else {"mode": "offline"},
        "summary": aggregate(rows),
        "cases": rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    # Also write a stable tracked copy for offline mode
    if args.mode == "offline":
        tracked = ROOT / "artifacts" / "hackathon" / "benchmark_offline.json"
        tracked.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(f"wrote {tracked}")

    print(json.dumps({"summary": report["summary"], "n": len(rows), "out": str(out)}, indent=2))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
