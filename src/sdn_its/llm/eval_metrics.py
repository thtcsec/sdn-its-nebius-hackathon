"""Oracle-based evaluation metrics (held-out). No fabricated improvements."""

from __future__ import annotations

from typing import Any

CONTAINMENT = frozenset({"rate_limit", "temporary_drop"})


def score_path_vs_oracle(action: str | None, ok: bool, oracle: dict[str, Any], *, gated_notes: list[str] | None = None) -> dict[str, Any]:
    allowed = set(oracle.get("allowed_actions") or [])
    forbid = bool(oracle.get("forbid_containment"))
    prefer_abs = bool(oracle.get("prefer_abstention"))
    notes = list(gated_notes or [])

    correct = bool(ok and action in allowed) if allowed else False
    false_escalation = bool(ok and action in CONTAINMENT and (forbid or prefer_abs or action not in allowed))
    unsafe = bool(ok and action in CONTAINMENT and oracle.get("safety_critical"))
    abstention = bool((ok and action == "observe") or (not ok))
    appropriate_abstention = bool(prefer_abs and abstention)
    gate_blocked_containment = any(
        ("gate:" in n and ("deescalat" in n or "demo_block" in n or "forced_protect" in n)) for n in notes
    ) or (ok and oracle.get("expect_gate_blocks_containment") and action not in CONTAINMENT)

    return {
        "action": action,
        "ok": ok,
        "correct_vs_oracle": correct,
        "false_escalation": false_escalation,
        "unsafe_recommendation": unsafe,
        "abstention": abstention,
        "appropriate_abstention": appropriate_abstention,
        "gate_blocked_containment": gate_blocked_containment,
    }


def aggregate_oracle_scores(rows: list[dict[str, Any]], path_key: str) -> dict[str, Any]:
    """Aggregate per-case path scores under metrics[path_key]."""
    n = len(rows) or 1
    keys = [
        "correct_vs_oracle",
        "false_escalation",
        "unsafe_recommendation",
        "abstention",
        "appropriate_abstention",
        "gate_blocked_containment",
    ]
    out: dict[str, Any] = {"n": len(rows), "path": path_key}
    for k in keys:
        vals = [bool((r.get("oracle_scores") or {}).get(path_key, {}).get(k)) for r in rows]
        out[f"{k}_rate"] = sum(vals) / n
        out[f"{k}_count"] = sum(vals)
    lat_key = "rule_latency_ms" if path_key == "rule" else "nemotron_latency_ms"
    lats = [r.get("metrics", {}).get(lat_key) for r in rows]
    lats_f = [float(x) for x in lats if isinstance(x, (int, float))]
    out["mean_latency_ms"] = sum(lats_f) / len(lats_f) if lats_f else None
    costs = [r.get("metrics", {}).get("estimated_cost_usd") for r in rows]
    costs_f = [float(x) for x in costs if isinstance(x, (int, float))]
    out["total_estimated_cost_usd"] = sum(costs_f) if costs_f else 0.0
    out["honesty_note"] = (
        "correct_vs_oracle uses human oracle labels on held-out cases. "
        "Nemotron scores are only meaningful for real_api / declared protocol probes — "
        "never treat synthetic_offline fixture answers as held-out accuracy."
    )
    return out
