"""Console / experiment Markdown report helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sdn_its.utils.paths import PROJECT_ROOT


def write_markdown_report(
    metrics: Mapping[str, Any],
    out_path: str | Path,
    title: str = "SDN-ITS Experiment Report",
    extra_sections: dict[str, str] | None = None,
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
        elif isinstance(v, dict | list):
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
    text = "\n".join(lines)
    out.write_text(text, encoding="utf-8")
    json_side = out.with_suffix(".json")
    json_side.write_text(json.dumps(dict(metrics), indent=2, default=str), encoding="utf-8")
    return out


def _fmt_pct(v: Any) -> str:
    try:
        return f"{float(v) * 100:.2f}%"
    except (TypeError, ValueError):
        return "—"


def build_console_report_markdown(controller: Any) -> tuple[str, dict[str, Any]]:
    """Rich console snapshot used by export + preview APIs."""
    from sdn_its.ai.empirical import load_empirical_metrics
    from sdn_its.ai.live_scorer import get_live_scorer

    scorer = get_live_scorer().status()
    emp = load_empirical_metrics()
    of: dict[str, Any] = {}
    try:
        of = controller.openflow_status(refresh=True)
    except Exception as exc:
        of = {"error": str(exc)}

    runtime = dict(getattr(controller, "runtime_settings", {}) or {})
    stats = dict(getattr(controller, "stats", {}) or {})
    samples = list(getattr(controller, "latency_samples_ms", []) or [])
    mit_log = list(getattr(controller, "mitigation_log", []) or [])[-15:]

    try:
        network_evidence = bool(controller.network_evidence_available())
    except Exception:
        network_evidence = False
    policy_samples = list(
        getattr(controller, "policy_latency_samples_ms", None) or samples
    )
    infer_samples = list(getattr(controller, "infer_latency_samples_ms", []) or [])

    metrics: dict[str, Any] = {
        "alerts": stats.get("total_alerts_received"),
        "policy_decisions": stats.get("policy_decisions", stats.get("total_alerts_received")),
        "mitigations": stats.get("mitigations_applied"),
        "fp_avoided": stats.get("rush_hour_policy_preserves", stats.get("false_positives_avoided")),
        "infer_calls": stats.get("infer_calls"),
        "active_rules": len(controller.flow_mgr.active_rules),
        "of_rules_installed": stats.get("of_rules_installed", 0),
        "network_evidence": network_evidence,
        "tau": scorer.get("tau"),
        "model_loaded": scorer.get("loaded"),
        "lab_mode": runtime.get("lab_mode"),
        "scenario_override": runtime.get("scenario_override"),
        "of_backend": getattr(controller, "of_backend_name", of.get("backend")),
        "of_connected": of.get("connected"),
        "latency_n": len(policy_samples),
        "infer_latency_n": len(infer_samples),
        "insdn_cls_f1": (emp.get("insdn_in_domain") or {}).get("cls_binary_f1"),
        "cic_zero_shot_f1": (emp.get("cic_zero_shot") or {}).get("cls_binary_f1"),
        "cic_adapted_f1": (emp.get("cic_adapted") or {}).get("cls_binary_f1"),
    }
    if policy_samples:
        import numpy as np

        arr = np.asarray(policy_samples, dtype=float)
        metrics["latency_p50_ms"] = float(np.percentile(arr, 50))
        metrics["latency_p95_ms"] = float(np.percentile(arr, 95))
        metrics["latency_mean_ms"] = float(arr.mean())

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# Reversible Mitigation Testbed — Console Snapshot",
        "",
        f"_Generated: {ts}_",
        "",
        "> Counters below are **software/policy** evidence unless `network_evidence=true`.",
        "",
        "## Runtime",
        "",
        f"- **Lab mode:** `{runtime.get('lab_mode')}`",
        f"- **Scenario override:** `{runtime.get('scenario_override')}`",
        f"- **Theme / role:** `{runtime.get('theme')}` / `{runtime.get('role_mode')}`",
        f"- **Dataset mode:** `{runtime.get('dataset_mode')}`",
        f"- **τ / k·σ:** `{scorer.get('tau')}` / `{runtime.get('k_sigma')}`",
        f"- **Model loaded:** `{scorer.get('loaded')}`",
        f"- **Network evidence:** `{network_evidence}`",
        "",
        "## Controller counters",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Policy decisions | {metrics['policy_decisions']} |",
        f"| Policy rule intents generated | {metrics['mitigations']} |",
        f"| Rush-hour preserved by policy | {metrics['fp_avoided']} |",
        f"| Infer calls (`/api/v1/infer`) | {metrics['infer_calls']} |",
        f"| Pending / in-memory rules | {metrics['active_rules']} |",
        f"| OF rules installed (acked) | {metrics['of_rules_installed']} |",
        f"| Policy latency samples | {metrics['latency_n']} |",
    ]
    if "latency_p50_ms" in metrics:
        lines.append(f"| Policy p50 (in-process) | {metrics['latency_p50_ms']:.3f} ms |")
        lines.append(f"| Policy p95 (in-process) | {metrics['latency_p95_ms']:.3f} ms |")
        lines.append("| Latency note | Not switch-install / not E2E PacketIn→mitigation |")

    lines.extend(
        [
            "",
            "## OpenFlow backend",
            "",
            f"- **Configured:** `{metrics['of_backend']}`",
            f"- **Connected:** `{metrics['of_connected']}`",
            f"- **Flow mods:** `{of.get('flow_mods')}`",
            f"- **Datapaths / bridges:** `{of.get('datapaths') or list((of.get('bridges') or {}).keys())}`",
            "",
        ]
    )
    bridges = of.get("bridges") or {}
    if bridges:
        lines.extend(["### OVS flow samples", "", "```"])
        for br, info in bridges.items():
            for ln in (info or {}).get("sample") or []:
                lines.append(f"{br}  {ln}")
        lines.extend(["```", ""])

    lines.extend(
        [
            "## Empirical evaluation (classifier head)",
            "",
            "| Eval | n | Acc | F1 | AUC |",
            "|------|---|-----|----|-----|",
        ]
    )
    for name, key in (
        ("InSDN in-domain", "insdn_in_domain"),
        ("CIC zero-shot", "cic_zero_shot"),
        ("CIC adapted", "cic_adapted"),
    ):
        m = emp.get(key) or {}
        lines.append(
            f"| {name} | {m.get('n_test', '—')} | {_fmt_pct(m.get('cls_binary_accuracy'))} | "
            f"{_fmt_pct(m.get('cls_binary_f1'))} | {_fmt_pct(m.get('roc_auc'))} |"
        )

    lines.extend(["", "### Notes", ""])
    for note in emp.get("notes") or []:
        lines.append(f"- {note}")

    lines.extend(["", "## Recent mitigations", ""])
    if not mit_log:
        lines.append("_No mitigations in this process yet._")
    else:
        lines.extend(
            [
                "| Time (UTC approx) | Alert | Attack | Status | OF ok |",
                "|-------------------|-------|--------|--------|-------|",
            ]
        )
        for e in reversed(mit_log):
            lines.append(
                f"| {datetime.fromtimestamp(e.get('ts', 0), tz=timezone.utc).strftime('%H:%M:%S')} | "
                f"{e.get('alert_id')} | {e.get('attack_type')} | {e.get('mitigation_status')} | "
                f"{e.get('of_ok')} |"
            )

    lines.extend(["", "## Active rules", ""])
    rules = controller.flow_mgr.get_all_active_rules()
    if not rules:
        lines.append("_None — forwarding nominal._")
    else:
        lines.extend(["| Rule | DPID | Match | Action | TTL |", "|------|------|-------|--------|-----|"])
        for r in rules:
            lines.append(
                f"| {r.get('rule_id')} | …{str(r.get('dpid', ''))[-4:]} | {r.get('src_ip') or 'GLOBAL'} | "
                f"{r.get('action')} | {r.get('remaining_cooldown_sec')}s |"
            )

    lines.extend(
        [
            "",
            "## Honesty / scope",
            "",
            "- This snapshot is from the **research ops console**, not a production ITS deployment.",
            "- Windows demo OF path may be `mock`; Lab mode + `SDN_OF_BACKEND=http` uses real ovs-ofctl via WSL agent.",
            "- Prefer **classifier-head** metrics over RE-threshold alone when citing detection quality.",
            "",
            "## Raw JSON",
            "",
            "```json",
            json.dumps(metrics, indent=2, default=str),
            "```",
            "",
        ]
    )
    return "\n".join(lines), metrics


def write_console_report(controller: Any, out_rel: str | Path) -> tuple[Path, str, dict[str, Any]]:
    markdown, metrics = build_console_report_markdown(controller)
    out = Path(out_rel)
    if not out.is_absolute():
        out = PROJECT_ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    out.with_suffix(".json").write_text(json.dumps(metrics, indent=2, default=str), encoding="utf-8")
    return out, markdown, metrics
