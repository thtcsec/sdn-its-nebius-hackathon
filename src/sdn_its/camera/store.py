"""In-memory camera context store + bounded RTSP worker.

Loads allow-listed cameras from configs/cameras.yaml (not env sprawl).
Does not archive video — at most one overwritten JPEG per selected camera.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .config import ROOT, load_camera_config, load_selected_cameras
from .detector import get_detector, reset_detector
from .models import CameraCard, CameraHealth, StreamQuality, TrafficContext, VisualActivity
from .rtsp_probe import grab_latest_frame, probe_stream

_STORE: CameraContextStore | None = None
_LOCK = threading.Lock()


def get_camera_store(*, reload: bool = False) -> CameraContextStore:
    global _STORE
    with _LOCK:
        if reload and _STORE is not None:
            _STORE.stop()
            _STORE = None
            reset_detector()
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
        self._detector_cfg = dict(self._cfg.get("detector") or {})
        # Resolve relative weights under project root
        w = self._detector_cfg.get("weights")
        if w and not Path(str(w)).is_absolute():
            self._detector_cfg["weights"] = str(ROOT / w)
        self._use_detector = self._physical_mode in {"rtsp_detector", "detector"} and bool(
            self._detector_cfg.get("enabled", True)
        )
        self._proxy: dict[str, dict[str, Any]] = {}
        self._frame_dir.mkdir(parents=True, exist_ok=True)
        (ROOT / "models" / "detectors").mkdir(parents=True, exist_ok=True)
        for cam in cameras or _default_cameras():
            self._health[cam.camera_id] = cam
            self._ctx[cam.camera_id] = TrafficContext(
                camera_id=cam.camera_id,
                visible_vehicle_tracks=4,
                vehicle_count=4,
                vehicle_flow_count=None,
                queue_length_m=5.0,
                mean_speed_kmh=38.0,
                context_reliability=0.5,
                confidence=0.0,
                source="synthetic",
                is_vehicle_count=True,
                activity_band="low",
                analytics_valid=True,
                reliability_components={"synthetic": True},
            )
            self._hydrate_frame_unlocked(cam.camera_id)

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
        """Set demo/scripted physical scenario and publish immediately.

        Without an immediate emit, fusion_preview / anomaly_alert can still see the
        previous aggregate (often idle→stable) until the next probe tick — which
        breaks Cam·rush + network-inject demos.
        """
        with self._lock:
            self._scenario = scenario
            self._tick += 1
        self._emit_context()

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
                "visible_vehicle_tracks": 0,
                "vehicle_flow_count": None,
                "vehicle_count": 0,
                "queue_length_m": 0.0,
                "pedestrian_present": False,
                "incident": False,
                "physical_label": "unknown",
                "context_reliability": None,
                "confidence": None,
                "cameras": 0,
                "stale": True,
            }
        for c in contexts:
            c.refresh_age()
        any_real_vc = any(c.is_vehicle_count for c in contexts)
        vehicle_count = (
            sum(int(c.visible_vehicle_tracks if c.visible_vehicle_tracks is not None else (c.vehicle_count or 0)) for c in contexts)
            if any_real_vc
            else None
        )
        queue_vals = [
            float(c.queue_length_proxy_m if c.queue_length_proxy_m is not None else (c.queue_length_m or 0))
            for c in contexts
            if c.is_vehicle_count
        ]
        queue = max(queue_vals) if queue_vals else None
        occ_vals = [float(c.occupancy_ratio) for c in contexts if c.is_vehicle_count and c.occupancy_ratio is not None]
        occupancy = max(occ_vals) if occ_vals else None
        ped_counts = [int(c.pedestrian_count or 0) for c in contexts if c.is_vehicle_count]
        ped_n = max(ped_counts) if ped_counts else (1 if any(c.pedestrian_present for c in contexts) else 0)
        rel_vals = [float(c.context_reliability or 0) for c in contexts if c.is_vehicle_count]
        context_reliability = round(sum(rel_vals) / len(rel_vals), 3) if rel_vals else None
        bands = [c.activity_band for c in contexts]
        band = "unknown"
        for b in ("high", "medium", "low"):
            if b in bands:
                band = b
                break
        ped = any(c.pedestrian_present for c in contexts)
        incident = any(c.incident for c in contexts)
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
        analytics_valid = any(c.analytics_valid for c in contexts)
        energies = [
            float(c.visual_activity.value)
            for c in contexts
            if c.visual_activity and c.visual_activity.value is not None
        ]
        sources = [c.analytics_source or c.source for c in contexts if c.is_vehicle_count]
        return {
            "visible_vehicle_tracks": vehicle_count,
            "vehicle_flow_count": None,
            "vehicle_count": vehicle_count,
            "queue_length_m": round(queue, 1) if queue is not None else None,
            "queue_length_proxy_m": round(queue, 1) if queue is not None else None,
            "occupancy_ratio": round(occupancy, 3) if occupancy is not None else None,
            "pedestrian_count": int(ped_n),
            "is_vehicle_count": any_real_vc,
            "vehicle_count_is_real": any_real_vc,
            "context_reliability": context_reliability,
            "activity_band": band,
            "source": sources[0] if sources else None,
            "visual_activity": {
                "metric": "visual_activity_proxy",
                "value": round(max(energies), 2) if energies else None,
                "source": "aggregate",
                "is_vehicle_count": False,
                "activity_band": band,
            },
            "pedestrian_present": ped,
            "incident": incident,
            "physical_label": label,
            "confidence": None,  # deprecated — use context_reliability
            "cameras": len(contexts),
            "live_rtsp": live_n,
            "stream_available": live_n > 0,
            "frame_fresh": any(c.health.quality.frame_fresh for c in cards),
            "scene_valid": any(c.health.quality.scene_valid for c in cards),
            "analytics_valid": analytics_valid,
            "max_analytics_age_s": round(max(ages), 2),
            "stale": max(ages) > max(15.0, self._probe_interval * 2),
            "scenario": self.get_scenario(),
            "physical_mode": self._physical_mode,
            "honesty": (
                "Same-zone physical context for mitigation decisions: network demand vs observable "
                "transportation activity. Tracks/occupancy/queue are zone proxies — not surveyed meters, "
                "not DDoS detection, not labeled-video FP reduction (see Exp B/C/D)."
            ),
            "detector": get_detector(self._detector_cfg).status() if self._use_detector else {"enabled": False},
        }

    def _frame_path(self, camera_id: str) -> Path:
        # camera_id is allow-listed (cam1..camN); never take a free-form path from the client
        safe = "".join(ch for ch in camera_id if ch.isalnum() or ch in {"-", "_"})
        return self._frame_dir / f"latest_{safe}.jpg"

    def _hydrate_frame_unlocked(self, camera_id: str) -> None:
        """Reuse overwritten JPEG on disk so preview works before the next RTSP grab."""
        h = self._health.get(camera_id)
        if not h:
            return
        p = self._frame_path(camera_id)
        if p.is_file() and p.stat().st_size > 0:
            h.latest_frame = str(p)

    def latest_frame_path(self, camera_id: str) -> Path | None:
        """Absolute path to overwritten preview JPEG, if present."""
        with self._lock:
            if camera_id not in self._health:
                return None
            self._hydrate_frame_unlocked(camera_id)
            p = self._frame_path(camera_id)
            if p.is_file() and p.stat().st_size > 0:
                return p
            return None

    def list_cards(self) -> list[dict[str, Any]]:
        def _cam_key(cid: str) -> tuple[int, str]:
            digits = "".join(ch for ch in cid if ch.isdigit())
            return (int(digits) if digits else 10**9, cid)

        with self._lock:
            out: list[dict[str, Any]] = []
            for cid in sorted(self._health, key=_cam_key):
                self._hydrate_frame_unlocked(cid)
                row = self._card_unlocked(cid).to_dict()
                p = self._frame_path(cid)
                if p.is_file() and p.stat().st_size > 0:
                    row["preview_url"] = f"/api/v1/camera/{cid}/preview"
                    row["preview_mtime"] = int(p.stat().st_mtime)
                out.append(row)
            return out

    def snapshot(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "research_role": (
                "Same RSU-zone physical-context sensor (RTSP → YOLO+IoU) for cyber–physical mitigation policy. "
                "Not a DDoS/vision detector · not surveyed veh/h · not labeled-FP proof. "
                "Scripted scenario replay = primary reproducible demo; live RTSP = sensor-pipeline bonus."
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
                    "select_mode",
                    "anonymize_labels",
                    "local_override",
                    "fallback",
                    "error",
                    "note",
                )
            },
            "detector": get_detector(self._detector_cfg).status() if self._use_detector else {"enabled": False},
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

    def _probe_one(self, cam_id: str, url: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
        info = probe_stream(url, timeout_s=self._ffprobe_t)
        frame_info: dict[str, Any] = {}
        if info.get("ok") and self._sample_frames:
            frame_info = grab_latest_frame(
                url,
                self._frame_path(cam_id),
                timeout_s=self._ffmpeg_t,
                max_bytes=self._frame_max,
            )
        return cam_id, info, frame_info

    def _apply_probe_result(
        self, cam_id: str, info: dict[str, Any], frame_info: dict[str, Any]
    ) -> None:
        h = self._health.get(cam_id)
        if not h:
            return
        stream_ok = bool(info.get("ok"))
        h.connected = stream_ok
        h.latency_ms = info.get("latency_ms")
        h.last_error = None if stream_ok else info.get("error")
        if stream_ok:
            h.codec = info.get("codec") or h.codec
            h.resolution = info.get("resolution") or h.resolution
            h.fps_cfg = info.get("fps") or h.fps_cfg
            h.mode = "rtsp_health"
        frame_ok = bool(frame_info.get("ok"))
        scene_ok = bool(frame_info.get("scene_valid")) if frame_ok else False
        analytics_ok = bool(frame_info.get("analytics_valid")) if frame_ok else False
        note = frame_info.get("note") if frame_ok else (frame_info.get("error") or info.get("error"))
        # Keep last good JPEG for preview even if this grab failed
        self._hydrate_frame_unlocked(cam_id)
        h.quality = StreamQuality(
            stream_available=stream_ok,
            frame_fresh=frame_ok,
            scene_valid=scene_ok,
            analytics_valid=analytics_ok and scene_ok,
            mean_luma=frame_info.get("mean_luma") if frame_ok else None,
            note=str(note)[:180] if note else None,
        )
        if frame_ok:
            h.latest_frame = frame_info.get("path") or str(self._frame_path(cam_id))
            h.latency_ms = frame_info.get("latency_ms") or h.latency_ms
            self._proxy[cam_id] = frame_info
        elif self._sample_frames and stream_ok:
            h.last_error = frame_info.get("error") or h.last_error
            # Keep prior proxy if frame still on disk; clear only when no preview exists
            if not h.latest_frame:
                self._proxy.pop(cam_id, None)

    def _probe_all(self) -> None:
        with self._lock:
            items = [
                (c.camera_id, c.rtsp_url, c.mode, c.role)
                for c in self._health.values()
            ]
        if self._cfg.get("probe_primary_first", True):
            items.sort(key=lambda t: 0 if t[3] == "primary" else 1)
        work = [(cid, url) for cid, url, mode, _r in items if url and mode != "disabled"]
        if not work:
            return
        # Parallel grab so all previews appear ~one RTSP timeout, not 3× serial
        results: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        with ThreadPoolExecutor(max_workers=min(3, len(work))) as pool:
            futs = [pool.submit(self._probe_one, cid, url) for cid, url in work]
            for fut in as_completed(futs):
                try:
                    results.append(fut.result())
                except Exception as exc:  # noqa: BLE001
                    # Should be rare — probe helpers already catch
                    results.append(("", {"ok": False, "error": str(exc)[:200]}, {}))
        with self._lock:
            for cam_id, info, frame_info in results:
                if not cam_id:
                    continue
                self._apply_probe_result(cam_id, info, frame_info)

        # Serial YOLO on GPU (avoid concurrent CUDA from parallel workers)
        if self._use_detector:
            det = get_detector(self._detector_cfg)
            for cam_id, _info, frame_info in results:
                if not cam_id or not frame_info.get("ok"):
                    continue
                path = Path(frame_info.get("path") or self._frame_path(cam_id))
                det_out = det.detect(path, camera_id=cam_id)
                with self._lock:
                    proxy = self._proxy.get(cam_id)
                    if isinstance(proxy, dict):
                        proxy["detection"] = det_out
                        if det_out.get("ok"):
                            h = self._health.get(cam_id)
                            if h:
                                h.quality.analytics_valid = True
                                h.quality.scene_valid = True
                                h.quality.note = (
                                    f"{det_out.get('source')} tracks={det_out.get('visible_vehicle_tracks')} "
                                    f"rel={det_out.get('context_reliability')} "
                                    f"occ={det_out.get('occupancy_ratio')} "
                                    f"dev={det_out.get('device')} {det_out.get('infer_ms')}ms"
                                )

    def _emit_synthetic(self) -> None:
        """Force one context publish tick (Exp B/C / tests)."""
        self._tick += 1
        self._emit_context()

    def _emit_context(self) -> None:
        with self._lock:
            scenario = self._scenario
            ids = list(self._health.keys())
            mode = self._physical_mode
        for i, cid in enumerate(ids):
            with self._lock:
                h = self._health[cid]
                proxy = self._proxy.get(cid)
            # Scenario buttons override live proxy (demo / Exp B-C) — synthetic counts ARE labeled real for rule tests
            if scenario and scenario != "idle":
                ctx = _synth_context(cid, scenario, self._tick, phase=i)
                self.publish(ctx)
                continue

            det = (proxy or {}).get("detection") if isinstance(proxy, dict) else None
            va_raw = (proxy or {}).get("visual_activity") if isinstance(proxy, dict) else None
            va = None
            if isinstance(va_raw, dict):
                va = VisualActivity(
                    metric=str(va_raw.get("metric") or "visual_activity_proxy"),
                    value=va_raw.get("value"),
                    source=str(va_raw.get("source") or "edge_energy"),
                    is_vehicle_count=False,
                    activity_band=str(va_raw.get("activity_band") or proxy.get("activity_band") or "unknown"),
                )

            # Prefer real YOLO counts when physical_mode=rtsp_detector
            if (
                mode in {"rtsp_detector", "detector"}
                and h.connected
                and isinstance(det, dict)
                and det.get("ok")
                and det.get("is_vehicle_count")
            ):
                vc = int(
                    det.get("visible_vehicle_tracks")
                    if det.get("visible_vehicle_tracks") is not None
                    else (det.get("vehicle_count") or 0)
                )
                qproxy = float(
                    det.get("queue_length_proxy_m")
                    if det.get("queue_length_proxy_m") is not None
                    else (det.get("queue_length_m_est") or 0.0)
                )
                band = str(det.get("activity_band") or ("high" if vc >= 25 else "medium" if vc >= 12 else "low"))
                cong = "high" if band == "high" else ("medium" if band == "medium" else "low")
                ctx = TrafficContext(
                    camera_id=cid,
                    visible_vehicle_tracks=vc,
                    vehicle_flow_count=det.get("vehicle_flow_count"),
                    vehicle_count=vc,
                    queue_length_m=qproxy,
                    queue_length_proxy_m=qproxy,
                    occupancy_ratio=det.get("occupancy_ratio"),
                    mean_speed_kmh=18.0 if band == "high" else 32.0,
                    pedestrian_present=bool(det.get("pedestrian_present")),
                    pedestrian_count=int(det.get("pedestrian_count") or 0),
                    incident=False,
                    congestion_level=cong,
                    context_reliability=float(det.get("context_reliability") or 0.0),
                    reliability_components=dict(det.get("reliability_components") or {}),
                    confidence=0.0,
                    source=str(det.get("source") or "detector_tracker_v1"),
                    analytics_source=str(det.get("source") or "detector_tracker_v1"),
                    is_vehicle_count=True,
                    visual_activity=va,
                    activity_band=band,
                    analytics_valid=True,
                    counts_by_class=dict(det.get("counts_by_class") or {}),
                    detector_device=str(det.get("device")) if det.get("device") is not None else None,
                    detector_infer_ms=det.get("infer_ms"),
                )
            elif mode in {"rtsp_proxy", "rtsp_detector"} and h.connected and va is not None:
                band = va.activity_band
                cong = "high" if band == "high" else ("medium" if band == "medium" else "low")
                ctx = TrafficContext(
                    camera_id=cid,
                    vehicle_count=None,
                    queue_length_m=None,
                    mean_speed_kmh=None,
                    pedestrian_present=False,
                    incident=False,
                    congestion_level=cong,
                    confidence=0.45 if h.quality.analytics_valid else 0.2,
                    source="rtsp_proxy",
                    is_vehicle_count=False,
                    visual_activity=va,
                    activity_band=band,
                    analytics_valid=bool(h.quality.analytics_valid),
                )
            elif mode in {"rtsp_proxy", "rtsp_detector"} and h.connected:
                ctx = TrafficContext(
                    camera_id=cid,
                    vehicle_count=None,
                    queue_length_m=None,
                    source="rtsp_live_no_proxy",
                    is_vehicle_count=False,
                    activity_band="unknown",
                    analytics_valid=False,
                    confidence=0.2,
                    congestion_level="low",
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
    """Synthetic placeholders only when inventory is missing — generic cam1/cam2."""
    return [
        CameraHealth(
            camera_id="cam1",
            label="cam1",
            junction="",
            codec="H.264",
            resolution="1280x720",
            fps_cfg=15.0,
            mode="synthetic",
            connected=True,
            role="primary",
            network_priority="HIGH",
        ),
        CameraHealth(
            camera_id="cam2",
            label="cam2",
            junction="",
            codec="H.264",
            resolution="1280x720",
            fps_cfg=12.0,
            mode="synthetic",
            connected=True,
            network_priority="HIGH",
        ),
    ]


def _synth_context(camera_id: str, scenario: str, tick: int, phase: int = 0) -> TrafficContext:
    """Synthetic scenario inputs for Exp B/C — vehicle_count is intentional and flagged real."""
    wobble = (tick + phase * 3) % 5

    def _vc(**kwargs: Any) -> TrafficContext:
        band = kwargs.pop("activity_band", None)
        vc = int(kwargs.get("vehicle_count") or kwargs.get("visible_vehicle_tracks") or 0)
        if band is None:
            band = "high" if vc >= 25 else ("medium" if vc >= 12 else "low")
        kwargs.setdefault("visible_vehicle_tracks", vc)
        kwargs.setdefault("vehicle_count", vc)
        kwargs.setdefault("vehicle_flow_count", None)
        kwargs.setdefault("context_reliability", 0.5)
        kwargs.setdefault(
            "reliability_components",
            {"synthetic": True, "note": "scripted scenario — not detector scores"},
        )
        return TrafficContext(
            is_vehicle_count=True,
            analytics_valid=True,
            activity_band=band,
            source="synthetic",
            **kwargs,
        )

    if scenario in {"rush", "legitimate_surge"}:
        return _vc(
            camera_id=camera_id,
            vehicle_count=28 + wobble,
            queue_length_m=42.0 + wobble,
            mean_speed_kmh=12.0,
            pedestrian_present=False,
            incident=False,
            congestion_level="high",
            confidence=0.0,
        )
    if scenario in {"attack_physical_stable", "attack"}:
        return _vc(
            camera_id=camera_id,
            vehicle_count=5 + (wobble % 2),
            queue_length_m=6.0,
            mean_speed_kmh=40.0,
            congestion_level="low",
            confidence=0.0,
        )
    if scenario == "mixed":
        return _vc(
            camera_id=camera_id,
            vehicle_count=30 + wobble,
            queue_length_m=48.0,
            mean_speed_kmh=10.0,
            pedestrian_present=True,
            congestion_level="high",
            confidence=0.0,
        )
    if scenario == "incident":
        return _vc(
            camera_id=camera_id,
            vehicle_count=18,
            queue_length_m=55.0,
            mean_speed_kmh=3.0,
            pedestrian_present=True,
            incident=True,
            congestion_level="high",
            confidence=0.0,
        )
    return _vc(
        camera_id=camera_id,
        vehicle_count=4 + wobble,
        queue_length_m=5.0 + wobble,
        mean_speed_kmh=36.0,
        congestion_level="low",
        confidence=0.0,
    )
