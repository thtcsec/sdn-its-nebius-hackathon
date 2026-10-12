"""Load public/synthetic hackathon incident fixtures (no RTSP / no secrets)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sdn_its.utils.paths import PROJECT_ROOT

FIXTURES_DIR = PROJECT_ROOT / "datasets" / "hackathon" / "incidents"


def list_incident_paths() -> list[Path]:
    if not FIXTURES_DIR.is_dir():
        return []
    return sorted(FIXTURES_DIR.glob("*.json"))


def load_incident(path: Path | str) -> dict[str, Any]:
    raw = str(path)
    candidates = [Path(raw), FIXTURES_DIR / raw]
    if not raw.endswith(".json"):
        candidates.append(FIXTURES_DIR / f"{raw}.json")
    p = next((c for c in candidates if c.is_file()), None)
    if p is None:
        raise FileNotFoundError(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "id" not in data:
        raise ValueError(f"invalid incident fixture: {p}")
    try:
        data["_path"] = str(p.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        data["_path"] = str(p)
    return data


def load_all_incidents() -> list[dict[str, Any]]:
    return [load_incident(p) for p in list_incident_paths()]


def incident_summaries() -> list[dict[str, Any]]:
    out = []
    for inc in load_all_incidents():
        out.append(
            {
                "id": inc["id"],
                "title": inc.get("title"),
                "description": inc.get("description"),
                "network_prediction": inc.get("network_prediction"),
                "path": inc.get("_path"),
                "force_mode": inc.get("force_mode"),
            }
        )
    return out
