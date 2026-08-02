"""Physical-world traffic context models (no PII / no plate / no face)."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class VisualActivity:
    """Provenance-preserving visual metric — NOT a vehicle count unless detector says so."""

    metric: str = "visual_activity_proxy"
    value: float | None = None
    source: str = "edge_energy"  # edge_energy | detector | synthetic | none
    is_vehicle_count: bool = False
    activity_band: str = "unknown"  # low | medium | high | unknown

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TrafficContext:
    """Edge analytics output for fusion.

    Honest rule:
    - ``vehicle_count`` / ``queue_length_m`` only when ``is_vehicle_count`` is True
      (synthetic scenario OR real detector/tracker).
    - RTSP edge-energy fills ``visual_activity`` only.
    """

    camera_id: str
    vehicle_count: int | None = None
    queue_length_m: float | None = None
    mean_speed_kmh: float | None = None
    pedestrian_present: bool = False
    incident: bool = False
    congestion_level: str = "low"  # low | medium | high
    confidence: float = 0.0
    source: str = "synthetic"  # synthetic | rtsp_proxy | detector | manual
    is_vehicle_count: bool = False
    visual_activity: VisualActivity | None = None
    activity_band: str = "unknown"
    analytics_valid: bool = False
    ts: float = field(default_factory=time.time)
    analytics_age_s: float = 0.0

    def refresh_age(self) -> None:
        self.analytics_age_s = max(0.0, time.time() - self.ts)

    def to_dict(self) -> dict[str, Any]:
        self.refresh_age()
        d = asdict(self)
        # Explicit anti-overclaim for UI
        d["vehicle_count_is_real"] = bool(self.is_vehicle_count and self.vehicle_count is not None)
        if not self.is_vehicle_count:
            d["vehicle_count"] = None
            d["queue_length_m"] = None
        return d

    @property
    def physical_label(self) -> str:
        if self.incident:
            return "incident"
        if self.pedestrian_present and (
            (self.is_vehicle_count and (self.vehicle_count or 0) >= 8)
            or self.activity_band in {"medium", "high"}
        ):
            return "mixed_busy"
        if self.is_vehicle_count:
            vc = int(self.vehicle_count or 0)
            q = float(self.queue_length_m or 0.0)
            if self.congestion_level == "high" or vc >= 25 or q >= 40:
                return "rush_hour"
            if vc >= 12 or q >= 20:
                return "elevated"
            return "stable"
        # Proxy path: band only
        if self.activity_band == "high" or self.congestion_level == "high":
            return "rush_hour"
        if self.activity_band == "medium":
            return "elevated"
        if self.activity_band == "low":
            return "stable"
        return "unknown"


@dataclass
class StreamQuality:
    """Separate connectivity from semantic analytics quality."""

    stream_available: bool = False
    frame_fresh: bool = False
    scene_valid: bool = False
    analytics_valid: bool = False
    mean_luma: float | None = None
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
    quality: StreamQuality = field(default_factory=StreamQuality)

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
            # Always advertise preview route when a frame path is known (file may be stale on disk).
            "preview_url": (
                f"/api/v1/camera/{self.camera_id}/preview" if self.latest_frame else None
            ),
            "preview_mtime": None,
            "quality": self.quality.to_dict(),
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
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        hostpart = rest.split("@", 1)[-1]
        return f"{scheme}://***@{hostpart}"
    return url
