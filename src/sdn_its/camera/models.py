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
    - ``visible_vehicle_tracks`` when detector/tracker ran (not veh/h flow count).
    - ``vehicle_flow_count`` only after line-crossing tracker exists (usually None).
    - RTSP edge-energy fills ``visual_activity`` only.
    """

    camera_id: str
    visible_vehicle_tracks: int | None = None
    vehicle_flow_count: int | None = None  # line-crossing only; usually unset
    vehicle_count: int | None = None  # deprecated alias of visible_vehicle_tracks
    queue_length_m: float | None = None
    mean_speed_kmh: float | None = None
    pedestrian_present: bool = False
    incident: bool = False
    congestion_level: str = "low"  # low | medium | high
    confidence: float = 0.0  # deprecated — use context_reliability
    context_reliability: float = 0.0
    reliability_components: dict[str, Any] = field(default_factory=dict)
    source: str = "synthetic"  # synthetic | rtsp_proxy | detector_tracker_v1 | …
    is_vehicle_count: bool = False  # True ⇒ tracks are detector-derived
    visual_activity: VisualActivity | None = None
    activity_band: str = "unknown"
    analytics_valid: bool = False
    counts_by_class: dict[str, int] = field(default_factory=dict)
    detector_device: str | None = None
    detector_infer_ms: float | None = None
    occupancy_ratio: float | None = None
    pedestrian_count: int | None = None
    queue_length_proxy_m: float | None = None
    analytics_source: str | None = None
    ts: float = field(default_factory=time.time)
    analytics_age_s: float = 0.0

    def refresh_age(self) -> None:
        self.analytics_age_s = max(0.0, time.time() - self.ts)

    def _tracks(self) -> int:
        if self.visible_vehicle_tracks is not None:
            return int(self.visible_vehicle_tracks)
        return int(self.vehicle_count or 0)

    def to_dict(self) -> dict[str, Any]:
        self.refresh_age()
        d = asdict(self)
        tracks = self._tracks() if self.is_vehicle_count else None
        d["visible_vehicle_tracks"] = tracks
        d["vehicle_flow_count"] = self.vehicle_flow_count  # usually None
        d["vehicle_count"] = tracks  # deprecated alias
        d["vehicle_count_is_real"] = bool(self.is_vehicle_count and tracks is not None)
        d["context_reliability"] = round(float(self.context_reliability or 0.0), 3)
        # Do not present deprecated confidence as calibrated probability
        d["confidence"] = None
        if not self.is_vehicle_count:
            d["visible_vehicle_tracks"] = None
            d["vehicle_count"] = None
            d["queue_length_m"] = None
            d["queue_length_proxy_m"] = None
            d["occupancy_ratio"] = None
            d["pedestrian_count"] = None
        else:
            if d.get("queue_length_proxy_m") is None and self.queue_length_m is not None:
                d["queue_length_proxy_m"] = self.queue_length_m
        return d

    @property
    def physical_label(self) -> str:
        if self.incident:
            return "incident"
        tracks = self._tracks()
        if self.pedestrian_present and (
            (self.is_vehicle_count and tracks >= 8) or self.activity_band in {"medium", "high"}
        ):
            return "mixed_busy"
        if self.is_vehicle_count:
            q = float(self.queue_length_proxy_m if self.queue_length_proxy_m is not None else (self.queue_length_m or 0.0))
            if self.congestion_level == "high" or tracks >= 25 or q >= 40:
                return "rush_hour"
            if tracks >= 12 or q >= 20:
                return "elevated"
            return "stable"
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
            "inventory_configured": bool(self.inventory_id),
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
