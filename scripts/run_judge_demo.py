#!/usr/bin/env python3
"""Judge-ready demo: ≥4 synthetic incidents, no RTSP, no TCN-GRU checkpoint.

Offline by default (synthetic Nemotron outputs). Pass ``--real`` to call Nebius
for non-forced fixtures using repository-root ``.env``.
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
from sdn_its.llm.audit_log import list_audit  # noqa: E402
from sdn_its.llm.fixtures import load_all_incidents  # noqa: E402
from sdn_its.utils.env import ensure_repo_env  # noqa: E402


def main() -> int:
    ensure_repo_env()
    parser = argparse.ArgumentParser(description="Judge demo — cyber-physical investigation")
    parser.add_argument("--real", action="store_true", help="Use real Nebius for non-forced fixtures")
    parser.add_argument("--limit", type=int, default=4, help="Minimum scenarios to run (default 4)")
    parser.add_argument(
        "--out",
        default=str(ROOT / "artifacts" / "hackathon" / "judge_demo_last.json"),
    )
    args = parser.parse_args()

    mode = "real" if args.real else "offline"
    incidents = load_all_incidents()
    if len(incidents) < args.limit:
        print(f"ERROR: need ≥{args.limit} fixtures, found {len(incidents)}", file=sys.stderr)
        return 1

    cases = []
    for inc in incidents:
        cases.append(
            investigate_case(inc, mode=mode, demo_mode=True, allow_containment_in_demo=False).to_dict()
        )

    # Highlight acceptance: unsafe escalation blocked
    unsafe = next((c for c in cases if c["incident_id"] == "07_unsafe_escalation_blocked"), None)
    gate_ok = bool(
        unsafe
        and unsafe["metrics"].get("gate_block_as_expected")
        and (unsafe["nemotron"].get("recommended_action") not in {"rate_limit", "temporary_drop"})
    )

    report = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "demo": "judge_cyber_physical_investigation_v1",
        "mode": mode,
        "classifier_note": (
            "This demo does NOT require tcn_gru_best.pt. Network labels come from "
            "fixture network_prediction (clearly synthetic / labeled). Console may show "
            "MODEL · DEGRADED for the research classifier — that is expected."
        ),
        "camera_note": "Synthetic same-zone camera metadata only — no private RTSP.",
        "of_backend": "mock",
        "acceptance": {
            "scenarios_run": len(cases),
            "unsafe_recommendation_blocked": gate_ok,
            "min_scenarios_met": len(cases) >= 4,
        },
        "cases": cases,
        "audit_tail": list_audit(limit=12),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report["acceptance"], indent=2))
    print(f"wrote {out}")
    return 0 if report["acceptance"]["min_scenarios_met"] and gate_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
