"""Load held-out evaluation cases (disjoint from regression fixtures)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sdn_its.utils.paths import PROJECT_ROOT

EVAL_DIR = PROJECT_ROOT / "datasets" / "hackathon" / "eval"
DEV_DIR = PROJECT_ROOT / "datasets" / "hackathon" / "incidents"


def load_eval_cases() -> list[dict[str, Any]]:
    if not EVAL_DIR.is_dir():
        return []
    cases = []
    for p in sorted(EVAL_DIR.glob("eval_*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("split") != "heldout_eval":
            raise ValueError(f"{p} missing split=heldout_eval")
        cases.append(data)
    return cases


def assert_disjoint_from_dev(cases: list[dict[str, Any]] | None = None) -> None:
    cases = cases if cases is not None else load_eval_cases()
    dev_ids = set()
    for p in DEV_DIR.glob("*.json"):
        try:
            dev_ids.add(json.loads(p.read_text(encoding="utf-8"))["id"])
        except Exception:
            continue
    overlap = {c["id"] for c in cases} & dev_ids
    if overlap:
        raise RuntimeError(f"eval/dev ID overlap: {sorted(overlap)}")


def select_real_api_subset(cases: list[dict[str, Any]], *, limit: int, budget_usd: float) -> list[dict[str, Any]]:
    """Pick non-protocol cases for live Nebius calls (stable order)."""
    eligible = [
        c
        for c in cases
        if not c.get("force_mode")
        and c.get("family")
        not in {"malformed_output", "api_outage", "unsafe_escalation"}
    ]
    # diversify by family
    picked: list[dict[str, Any]] = []
    seen_fam: set[str] = set()
    for c in eligible:
        fam = str(c.get("family"))
        if fam not in seen_fam:
            picked.append(c)
            seen_fam.add(fam)
        if len(picked) >= limit:
            break
    for c in eligible:
        if len(picked) >= limit:
            break
        if c not in picked:
            picked.append(c)
    # budget is enforced at runtime by cumulative cost; annotate intent
    for c in picked:
        c = dict(c)
    return picked[:limit]
