#!/usr/bin/env python3
"""Produce multi-step investigation traces for the four demo scenarios (offline by default)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from sdn_its.llm.agent import run_rule_only  # noqa: E402
from sdn_its.llm.multi_step import run_multi_step_investigation  # noqa: E402
from sdn_its.llm.scenarios import load_all_scenarios  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", action="store_true", help="Use Nebius for tool selection (costs money)")
    parser.add_argument("--allow-containment-in-demo", action="store_true")
    parser.add_argument(
        "--out",
        default=str(ROOT / "artifacts" / "hackathon" / "multistep_demo_traces.json"),
    )
    args = parser.parse_args()

    scenarios = load_all_scenarios()
    if len(scenarios) < 4:
        print("ERROR: need >=4 scenarios", file=sys.stderr)
        return 1

    mode = "real" if args.real else "offline"
    cases = []
    for sc in scenarios:
        rule = run_rule_only(sc)
        ms = run_multi_step_investigation(
            sc,
            mode=mode,  # type: ignore[arg-type]
            include_camera=True,
            apply_gate=True,
            demo_mode=not args.allow_containment_in_demo,
            allow_containment_in_demo=args.allow_containment_in_demo,
            rule_fusion=rule.fusion,
        )
        cases.append(
            {
                "scenario_id": sc["id"],
                "title": sc.get("title"),
                "story": sc.get("story"),
                "rule_action": rule.recommended_action,
                "investigation": ms.to_dict(),
            }
        )

    report = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "product_story": (
            "A network traffic surge is not always an attack. "
            "Investigate physical context before making disruptive decisions."
        ),
        "mode": mode,
        "of_backend": "mock",
        "honesty_note": (
            "Offline traces use deterministic_planner + real evidence tools. "
            "Camera fields are synthetic metadata. real mode only when --real."
        ),
        "n": len(cases),
        "cases": cases,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    tracked = ROOT / "artifacts" / "hackathon" / "multistep_demo_traces.json"
    if not args.real:
        tracked.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"n": len(cases), "mode": mode, "out": str(out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
