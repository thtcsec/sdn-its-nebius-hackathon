"""Markdown experiment / evaluation report writer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from sdn_its.utils.paths import PROJECT_ROOT


def write_markdown_report(
    metrics: Mapping[str, Any],
    out_path: str | Path,
    title: str = "SDN-ITS Experiment Report",
    extra_sections: Optional[Dict[str, str]] = None,
) -> Path:
    out = Path(out_path)
    if not out.is_absolute():
        out = PROJECT_ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# {title}",
        "",
        f"_Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}_",
        "",
        "## Metrics",
        "",
        "| Key | Value |",
        "|-----|-------|",
    ]
    for k, v in metrics.items():
        if isinstance(v, float):
            lines.append(f"| `{k}` | {v:.4f} |")
        elif isinstance(v, (dict, list)):
            lines.append(f"| `{k}` | `{json.dumps(v)[:120]}` |")
        else:
            lines.append(f"| `{k}` | {v} |")

    if extra_sections:
        for heading, body in extra_sections.items():
            lines.extend(["", f"## {heading}", "", body.strip(), ""])

    lines.extend(
        [
            "",
            "## Raw JSON",
            "",
            "```json",
            json.dumps(dict(metrics), indent=2, default=str),
            "```",
            "",
        ]
    )
    out.write_text("\n".join(lines), encoding="utf-8")
    json_side = out.with_suffix(".json")
    json_side.write_text(json.dumps(dict(metrics), indent=2, default=str), encoding="utf-8")
    return out
