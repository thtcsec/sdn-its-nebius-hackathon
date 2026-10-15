"""Treat incident telemetry / camera fields as untrusted input.

Malformed values must never crash fusion or tool paths, and must never
silently justify containment.
"""

from __future__ import annotations

import math
from typing import Any

_BAD_STRINGS = frozenset(
    {
        "",
        "nan",
        "none",
        "null",
        "n/a",
        "na",
        "...",
        "…",
        "not_a_number",
        "inf",
        "-inf",
        "+inf",
        "infinity",
        "undefined",
        "maybe",
        "unknown",
    }
)


def safe_float(
    value: Any,
    *,
    default: float | None = None,
    min_v: float | None = None,
    max_v: float | None = None,
) -> float | None:
    """Parse a finite float or return default. Never raises."""
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        f = float(value)
    elif isinstance(value, str):
        s = value.strip().lower()
        if s in _BAD_STRINGS:
            return default
        try:
            f = float(s)
        except ValueError:
            return default
    else:
        return default
    if math.isnan(f) or math.isinf(f):
        return default
    if min_v is not None:
        f = max(min_v, f)
    if max_v is not None:
        f = min(max_v, f)
    return f


def safe_int(value: Any, *, default: int | None = None, min_v: int | None = None, max_v: int | None = None) -> int | None:
    f = safe_float(value, default=None)
    if f is None:
        return default
    i = int(round(f))
    if min_v is not None:
        i = max(min_v, i)
    if max_v is not None:
        i = min(max_v, i)
    return i


def safe_bool(value: Any, *, default: bool | None = None) -> bool | None:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isnan(float(value)) or math.isinf(float(value)):
            return default
        return bool(value)
    if isinstance(value, str):
        s = value.strip().lower()
        if s in {"true", "yes", "1", "y"}:
            return True
        if s in {"false", "no", "0", "n"}:
            return False
        if s in _BAD_STRINGS:
            return default
    return default


def sanitize_telemetry(raw: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    """Normalize telemetry; collect issues. Sets _telemetry_unreliable when untrusted."""
    tel = dict(raw or {})
    issues: list[str] = []

    pin_raw = tel.get("packet_in_delta_pct")
    pin = safe_float(pin_raw, default=None, min_v=-100.0, max_v=10_000.0)
    if pin_raw is not None and pin is None:
        issues.append("invalid_packet_in_delta_pct")
    elif pin is not None and pin < 0:
        issues.append("negative_packet_in_delta_pct")
        pin = None

    dom_raw = tel.get("source_dominance")
    dom = safe_float(dom_raw, default=None, min_v=0.0, max_v=1.0)
    if dom_raw is not None and dom is None:
        issues.append("invalid_source_dominance")

    dist_raw = tel.get("distributed_sources")
    dist = safe_bool(dist_raw, default=None)
    if dist_raw is not None and dist is None:
        issues.append("invalid_distributed_sources")

    if str(tel.get("quality_flag") or "").lower() in {"unreliable", "corrupt", "bad"}:
        issues.append("quality_flag_unreliable")

    out = dict(tel)
    out["packet_in_delta_pct"] = pin
    out["source_dominance"] = dom
    out["distributed_sources"] = dist
    if issues:
        out["_telemetry_unreliable"] = True
        out["_sanitize_issues"] = issues
    else:
        out.pop("_telemetry_unreliable", None)
        out.pop("_sanitize_issues", None)
    return out, issues


def sanitize_camera(raw: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    """Normalize camera metadata; never raise on bad types."""
    cam = dict(raw or {})
    issues: list[str] = []
    out = dict(cam)

    tracks_raw = cam.get("visible_vehicle_tracks")
    if tracks_raw is not None:
        tracks = safe_int(tracks_raw, default=None, min_v=0, max_v=100_000)
        if tracks is None:
            issues.append("invalid_visible_vehicle_tracks")
            out["visible_vehicle_tracks"] = None
        else:
            out["visible_vehicle_tracks"] = tracks

    q_raw = cam.get("queue_length_proxy_m")
    if q_raw is None:
        q_raw = cam.get("queue_length_m")
    if q_raw is not None:
        q = safe_float(q_raw, default=None, min_v=0.0, max_v=10_000.0)
        if q is None:
            issues.append("invalid_queue_length")
            out["queue_length_proxy_m"] = None
        else:
            out["queue_length_proxy_m"] = q

    for bkey in ("stale", "stream_available", "analytics_valid", "pedestrian_present", "incident", "is_vehicle_count", "vehicle_count_is_real"):
        if bkey in cam and cam[bkey] is not None:
            b = safe_bool(cam[bkey], default=None)
            if b is None:
                issues.append(f"invalid_{bkey}")
            else:
                out[bkey] = b

    if issues:
        out["_camera_sanitize_issues"] = issues
    return out, issues
