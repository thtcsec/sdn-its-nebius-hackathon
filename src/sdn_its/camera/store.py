"""In-memory camera context store + bounded RTSP worker.

Loads allow-listed cameras from configs/cameras.yaml (not env sprawl).
Does not archive video — at most one overwritten JPEG per selected camera.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from .config import ROOT, load_camera_config, load_selected_cameras
from .models import CameraCard, CameraHealth, TrafficContext
from .rtsp_probe import grab_latest_frame, probe_stream

_STORE: CameraContextStore | None = None
_LOCK = threading.Lock()


def get_camera_store(*, reload: bool = False) -> CameraContextStore:
    global _STORE
    with _LOCK:
        if reload and _STORE is not None:
            _STORE.stop()
            _STORE = None
        if _STORE is None:
            _STORE = CameraContextStore.from_config()
            _STORE.start()
        return _STORE


class CameraContextStore:
    """Publishes TrafficContext for fusion. Prefer config allow-list + RTSP health."""

    def __init__(
        self,
        cameras: list[CameraHealth] | None = None,
        *,
        cfg: dict[str, Any] | None = None,
        load_meta: dict[str, Any] | None = None,
    ):
        self._lock = threading.RLock()
        self._health: dict[str, CameraHealth] = {}
        self._ctx: dict[str, TrafficContext] = {}
        self._scenario = "idle"
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()
        self._tick = 0
        self._cfg = cfg or {}
        self._load_meta = load_meta or {}
        self._physical_mode = str(self._cfg.get("physical_mode") or "synthetic")
        self._probe_interval = float(self._cfg.get("probe_interval_s") or 12)
        self._sample_frames = bool(self._cfg.get("sample_frames", False))
        self._frame_dir = ROOT / str(self._cfg.get("frame_dir") or "tmp/camera_frames")
        self._frame_max = int(self._cfg.get("frame_max_bytes") or 2_500_000)
        self._ffprobe_t = float(self._cfg.get("ffprobe_timeout_s") or 12)
        self._ffmpeg_t = float(self._cfg.get("ffmpeg_timeout_s") or 20)
        self._proxy: dict[str, dict[str, Any]] = {}
        for cam in cameras or _default_cameras():
            self._health[cam.camera_id] = cam
            self._ctx[cam.camera_id] = TrafficContext(
                camera_id=cam.camera_id,
                vehicle_count=4,
                queue_length_m=5.0,
                mean_speed_kmh=38.0,
                confidence=0.7,
                source="synthetic",
            )

    @classmethod
    def from_config(cls, path: Path | None = None) -> CameraContextStore:
        cfg = load_camera_config(path)
        cams, meta = load_selected_cameras(cfg)
        if not cams:
            # Fallback synthetic demos if inventory missing
            cams = _default_cameras()
            meta["fallback"] = "synthetic_defaults"
        return cls(cams, cfg=cfg, load_meta=meta)

    @classmethod
    def from_env(cls) -> CameraContextStore:
        """Back-compat alias — config file is the source of truth."""
        return cls.from_config()

    def start(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._stop.clear()
        self._worker = threading.Thread(target=self._loop, name="camera-context-worker", daemon=True)
        self._worker.start()

    def stop(self) -> None:
        self._stop.set()

    def set_scenario(self, scenario: str) -> None:
        with self._lock:
            self._scenario = scenario

    def get_scenario(self) -> str:
        with self._lock:
            return self._scenario

    def publish(self, ctx: TrafficContext) -> None:
        with self._lock:
            ctx.ts = time.time()
            self._ctx[ctx.camera_id] = ctx

    def aggregate_context(self) -> dict[str, Any]:
        with self._lock:
            cards = [self._card_unlocked(cid) for cid in self._health]
            contexts = [c.context for c in cards]
        if not contexts:
            return {
                "vehicle_count": 0,
                "queue_length_m": 0.0,
                "pedestrian_present": False,
                "incident": False,
                "physical_label": "unknown",
                "confidence": 0.0,
                "cameras": 0,
                "stale": True,
            }
        for c in contexts:
            c.refresh_age()
        vehicle_count = sum(c.vehicle_count for c in contexts)
        queue = max(c.queue_length_m for c in contexts)
        ped = any(c.pedestrian_present for c in contexts)
        incident = any(c.incident for c in contexts)
        conf = sum(c.confidence for c in contexts) / len(contexts)
        ages = [c.analytics_age_s for c in contexts]
        label = "stable"
        for c in contexts:
            if c.physical_label == "incident":
                label = "incident"
                break
            if c.physical_label == "rush_hour":
                label = "rush_hour"
            elif c.physical_label == "elevated" and label == "stable":
                label = "elevated"
            elif c.physical_label == "mixed_busy" and label in {"stable", "elevated"}:
                label = "mixed_busy"
        live_n = sum(1 for c in cards if c.health.connected)
        return {
            "vehicle_count": vehicle_count,
            "queue_length_m": round(queue, 1),
            "pedestrian_present": ped,
            "incident": incident,
            "physical_label": label,
            "confidence": round(conf, 3),
            "cameras": len(contexts),
            "live_rtsp": live_n,
            "max_analytics_age_s": round(max(ages), 2),
            "stale": max(ages) > max(15.0, self._probe_interval * 2),
            "scenario": self.get_scenario(),
            "physical_mode": self._physical_mode,
        }

    def list_cards(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._card_unlocked(cid).to_dict() for cid in sorted(self._health)]

    def snapshot(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "research_role": (
                "Allow-listed RTSP → health + optional proxy context for fusion. "
                "Not a video wall / not an archive."
            ),
            "scenario": self.get_scenario(),
            "aggregate": self.aggregate_context(),
            "cameras": self.list_cards(),
            "config": {
                k: self._load_meta.get(k)
                for k in (
                    "config_path",
                    "inventory",
                    "selected_ids",
                    "missing_ids",
                    "loaded",
                    "inventory_total",
                    "physical_mode",
                    "sample_frames",
                    "fallback",
                    "error",
                    "note",
                )
            },
            "bounds": {
                "max_cameras": self._cfg.get("max_cameras", 3),
                "probe_interval_s": self._probe_interval,
                "frame_dir": str(self._frame_dir),
                "sample_frames": self._sample_frames,
            },
        }

    def _card_unlocked(self, camera_id: str) -> CameraCard:
        return CameraCard(health=self._health[camera_id], context=self._ctx[camera_id])

    def _loop(self) -> None:
        # stagger: probe immediately, then interval
        while not self._stop.is_set():
            self._tick += 1
            self._probe_all()
            self._emit_context()
            if self._stop.wait(self._probe_interval):
                break

    def _probe_all(self) -> None:
        with self._lock:
            items = [
                (c.camera_id, c.rtsp_url, c.mode, c.role)
                for c in self._health.values()
            ]
        if self._cfg.get("probe_primary_first", True):
            items.sort(key=lambda t: 0 if t[3] == "primary" else 1)
        for cam_id, url, mode, _role in items:
            if not url or mode == "disabled":
                continue
            info = probe_stream(url, timeout_s=self._ffprobe_t)
            frame_info: dict[str, Any] = {}
            if info.get("ok") and self._sample_frames:
                dest = self._frame_dir / f"latest_{cam_id}.jpg"
                frame_info = grab_latest_frame(
                    url,
                    dest,
                    timeout_s=self._ffmpeg_t,
                    max_bytes=self._frame_max,
                )
            with self._lock:
                h = self._health.get(cam_id)
                if not h:
                    continue
                h.connected = bool(info.get("ok"))
                h.latency_ms = info.get("latency_ms")
                h.last_error = None if info.get("ok") else info.get("error")
                if info.get("ok"):
                    h.codec = info.get("codec") or h.codec
                    h.resolution = info.get("resolution") or h.resolution
                    h.fps_cfg = info.get("fps") or h.fps_cfg
                    h.mode = "rtsp_health"
                if frame_info.get("ok"):
                    h.latest_frame = frame_info.get("path")
                    h.latency_ms = frame_info.get("latency_ms") or h.latency_ms
                    self._proxy[cam_id] = frame_info
                elif self._sample_frames and info.get("ok"):
                    h.last_error = frame_info.get("error") or h.last_error

    def _emit_context(self) -> None:
        with self._lock:
            scenario = self._scenario
            ids = list(self._health.keys())
            mode = self._physical_mode
        for i, cid in enumerate(ids):
            with self._lock:
                h = self._health[cid]
                proxy = self._proxy.get(cid)
            # Scenario buttons override live proxy (demo / Exp B-C)
            if scenario and scenario != "idle":
                ctx = _synth_context(cid, scenario, self._tick, phase=i)
                self.publish(ctx)
                continue
            if mode == "rtsp_proxy" and h.connected and isinstance(proxy, dict) and proxy.get("vehicle_count_proxy") is not None:
                ctx = TrafficContext(
                    camera_id=cid,
                    vehicle_count=int(proxy["vehicle_count_proxy"]),
                    queue_length_m=float(proxy.get("queue_length_m_proxy") or 0),
                    mean_speed_kmh=18.0 if proxy.get("physical_label_proxy") == "rush_hour" else 35.0,
                    pedestrian_present=False,
                    incident=False,
                    congestion_level="high" if proxy.get("physical_label_proxy") == "rush_hour" else "low",
                    confidence=0.55,
                    source="rtsp_proxy",
                )
            elif mode == "rtsp_proxy" and h.connected:
                # Stream up but no frame proxy yet — mild elevated for primary
                base = 18 if h.role == "primary" or h.network_priority == "HIGH" else 6
                ctx = TrafficContext(
                    camera_id=cid,
                    vehicle_count=base,
                    queue_length_m=12.0 if base > 10 else 5.0,
                    mean_speed_kmh=25.0,
                    congestion_level="elevated" if base > 10 else "low",
                    confidence=0.5,
                    source="rtsp_live_no_proxy",
                )
            else:
                ctx = _synth_context(cid, scenario, self._tick, phase=i)
            self.publish(ctx)
            with self._lock:
                h2 = self._health.get(cid)
                if not h2:
                    continue
                if ctx.incident or ctx.pedestrian_present:
                    h2.network_priority = "CRITICAL"
                elif ctx.physical_label == "rush_hour" and h2.role == "primary":
                    h2.network_priority = "HIGH"


def _default_cameras() -> list[CameraHealth]:
    return [
        CameraHealth(
            camera_id="cam-j04",
            label="Junction 04 · synthetic",
            junction="J04",
            codec="H.264",
            resolution="1280x720",
            fps_cfg=15.0,
            mode="synthetic",
            connected=True,
            role="primary",
            network_priority="HIGH",
        ),
        CameraHealth(
            camera_id="cam-j04b",
            label="Junction 04 · pedestrian (synthetic)",
            junction="J04",
            codec="H.264",
            resolution="1280x720",
            fps_cfg=12.0,
            mode="synthetic",
            connected=True,
            network_priority="HIGH",
        ),
    ]


def _synth_context(camera_id: str, scenario: str, tick: int, phase: int = 0) -> TrafficContext:
    wobble = (tick + phase * 3) % 5
    if scenario in {"rush", "legitimate_surge"}:
        return TrafficContext(
            camera_id=camera_id,
            vehicle_count=28 + wobble,
            queue_length_m=42.0 + wobble,
            mean_speed_kmh=12.0,
            pedestrian_present=False,
            incident=False,
            congestion_level="high",
            confidence=0.9,
            source="synthetic",
        )
    if scenario in {"attack_physical_stable", "attack"}:
        return TrafficContext(
            camera_id=camera_id,
            vehicle_count=5 + (wobble % 2),
            queue_length_m=6.0,
            mean_speed_kmh=40.0,
            congestion_level="low",
            confidence=0.88,
            source="synthetic",
        )
    if scenario == "mixed":
        return TrafficContext(
            camera_id=camera_id,
            vehicle_count=30 + wobble,
            queue_length_m=48.0,
            mean_speed_kmh=10.0,
            pedestrian_present=True,
            congestion_level="high",
            confidence=0.91,
            source="synthetic",
        )
    if scenario == "incident":
        return TrafficContext(
            camera_id=camera_id,
            vehicle_count=18,
            queue_length_m=55.0,
            mean_speed_kmh=3.0,
            pedestrian_present=True,
            incident=True,
            congestion_level="high",
            confidence=0.93,
            source="synthetic",
        )
    return TrafficContext(
        camera_id=camera_id,
        vehicle_count=4 + wobble,
        queue_length_m=5.0 + wobble,
        mean_speed_kmh=36.0,
        congestion_level="low",
        confidence=0.75,
        source="synthetic",
    )
