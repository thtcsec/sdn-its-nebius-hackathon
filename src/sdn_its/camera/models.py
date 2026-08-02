"""Physical-world traffic context models (no PII / no plate / no face)."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TrafficContext:
    """Edge analytics output — what the fusion engine consumes."""

    camera_id: str
    vehicle_count: int = 0
    queue_length_m: float = 0.0
    mean_speed_kmh: float | None = None
    pedestrian_present: bool = False
    incident: bool = False
    congestion_level: str = "low"  # low | medium | high
    confidence: float = 0.0
    source: str = "synthetic"  # synthetic | opencv_proxy | detector | manual
    ts: float = field(default_factory=time.time)
    analytics_age_s: float = 0.0

    def refresh_age(self) -> None:
        self.analytics_age_s = max(0.0, time.time() - self.ts)

    def to_dict(self) -> dict[str, Any]:
        self.refresh_age()
        return asdict(self)

    @property
    def physical_label(self) -> str:
        if self.incident:
            return "incident"
        if self.pedestrian_present and self.vehicle_count >= 8:
            return "mixed_busy"
        if self.congestion_level == "high" or self.vehicle_count >= 25 or self.queue_length_m >= 40:
            return "rush_hour"
        if self.vehicle_count >= 12 or self.queue_length_m >= 20:
            return "elevated"
        return "stable"


@dataclass
class CameraHealth:
    camera_id: str
    label: str
    junction: str = ""
    rtsp_url: str | None = None
    connected: bool = False
    codec: str | None = None
    resolution: str | None = None
    fps_cfg: float | None = None
    latency_ms: float | None = None
    dropped_frames: int = 0
    network_priority: str = "NORMAL"  # NORMAL | HIGH | CRITICAL
    last_error: str | None = None
    mode: str = "synthetic"  # synthetic | rtsp_health | disabled
    inventory_id: str | None = None
    role: str = "secondary"
    latest_frame: str | None = None  # path to overwritten latest jpg (optional)

    def to_dict(self) -> dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "label": self.label,
            "junction": self.junction,
            "connected": self.connected,
            "mode": self.mode,
            "inventory_id": self.inventory_id,
            "role": self.role,
            "rtsp_configured": bool(self.rtsp_url),
            "rtsp_url_redacted": _redact_rtsp(self.rtsp_url),
            "codec": self.codec,
            "resolution": self.resolution,
            "fps_cfg": self.fps_cfg,
            "latency_ms": self.latency_ms,
            "dropped_frames": self.dropped_frames,
            "network_priority": self.network_priority,
            "last_error": self.last_error,
            "latest_frame": self.latest_frame,
        }


@dataclass
class CameraCard:
    health: CameraHealth
    context: TrafficContext

    def to_dict(self) -> dict[str, Any]:
        row = self.health.to_dict()
        row["context"] = self.context.to_dict()
        row["physical_label"] = self.context.physical_label
        return row


def _redact_rtsp(url: str | None) -> str | None:
    if not url:
        return None
    # hide credentials: rtsp://user:pass@host/path → rtsp://***@host/path
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        hostpart = rest.split("@", 1)[-1]
        return f"{scheme}://***@{hostpart}"
    return url
