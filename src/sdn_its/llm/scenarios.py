"""Load multi-step investigation demo scenarios (not held-out eval)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sdn_its.utils.paths import PROJECT_ROOT

SCENARIO_DIR = PROJECT_ROOT / "datasets" / "hackathon" / "scenarios"


def load_all_scenarios() -> list[dict[str, Any]]:
    if not SCENARIO_DIR.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(SCENARIO_DIR.glob("scenario_*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        if not data.get("id"):
            raise ValueError(f"scenario missing id: {p}")
        out.append(data)
    return out


def load_scenario(scenario_id: str) -> dict[str, Any]:
    sid = scenario_id if scenario_id.endswith(".json") else f"{scenario_id}.json"
    if not sid.startswith("scenario_") and not Path(sid).name.startswith("scenario_"):
        # allow bare id
        path = SCENARIO_DIR / f"{scenario_id}.json"
        if not path.is_file():
            path = SCENARIO_DIR / sid
    else:
        path = SCENARIO_DIR / Path(sid).name
    if not path.is_file():
        # try match by id field
        for s in load_all_scenarios():
            if s["id"] == scenario_id:
                return s
        raise FileNotFoundError(scenario_id)
    return json.loads(path.read_text(encoding="utf-8"))


def scenario_summaries() -> list[dict[str, str]]:
    return [
        {
            "id": s["id"],
            "title": str(s.get("title") or s["id"]),
            "story": str(s.get("story") or "")[:160],
            "kind": "scenario",
        }
        for s in load_all_scenarios()
    ]
