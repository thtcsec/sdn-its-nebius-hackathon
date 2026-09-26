"""YOLO + IoU tracker analytics (CUDA when available).

Pipeline: frame → detect → track → zone occupancy → queue proxy.
COCO vehicles + person count only — no plate / face / identity.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from .tracker import IoUTracker

# COCO: bicycle, car, motorcycle, bus, truck
_VEHICLE_CLASSES = (1, 2, 3, 5, 7)
_CLASS_NAMES = {
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}

_LOCK = threading.Lock()
_ENGINE: VehicleDetector | None = None


def get_detector(cfg: dict[str, Any] | None = None) -> VehicleDetector:
    global _ENGINE
    with _LOCK:
        if _ENGINE is None:
            _ENGINE = VehicleDetector(cfg or {})
        return _ENGINE


def reset_detector() -> None:
    global _ENGINE
    with _LOCK:
        _ENGINE = None


class VehicleDetector:
    """YOLOv8n + per-camera IoU tracker → detector_tracker_v1 schema."""

    SOURCE = "detector_tracker_v1"

    def __init__(self, cfg: dict[str, Any] | None = None):
        cfg = cfg or {}
        self.enabled = bool(cfg.get("enabled", True))
        self.weights = str(cfg.get("weights") or "yolov8n.pt")
        self.conf = float(cfg.get("conf") or 0.35)
        self.iou = float(cfg.get("iou") or 0.45)
        self.imgsz = int(cfg.get("imgsz") or 640)
        self.annotate = bool(cfg.get("annotate_preview", True))
        self.max_det = int(cfg.get("max_det") or 100)
        # Bottom fraction of frame treated as roadway zone for occupancy/queue
        self.zone_y0 = float(cfg.get("zone_y0") or 0.35)
        self.meters_per_norm_height = float(cfg.get("meters_per_norm_height") or 45.0)
        prefer = str(cfg.get("device") or "auto")
        self._device = self._resolve_device(prefer)
        self._model = None
        self._load_error: str | None = None
        self._last_ms: float | None = None
        self._trackers: dict[str, IoUTracker] = {}
        self._ped_trackers: dict[str, IoUTracker] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _resolve_device(prefer: str) -> str | int:
        import torch

        if prefer in {"cpu", "CPU"}:
            return "cpu"
        if prefer.startswith("cuda") or prefer in {"0", "gpu", "auto", ""}:
            if torch.cuda.is_available():
                return 0
        return "cpu"

    def status(self) -> dict[str, Any]:
        import torch

        return {
            "enabled": self.enabled,
            "weights": self.weights,
            "device": str(self._device),
            "cuda_available": bool(torch.cuda.is_available()),
            "cuda_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "loaded": self._model is not None,
            "load_error": self._load_error,
            "last_infer_ms": self._last_ms,
            "conf": self.conf,
            "source": self.SOURCE,
            "tracker": "iou_v1",
            "classes": list(_VEHICLE_CLASSES),
        }

    def _ensure_model(self) -> bool:
        if not self.enabled:
            self._load_error = "detector_disabled"
            return False
        if self._model is not None:
            return True
        try:
            from ultralytics import YOLO

            self._model = YOLO(self.weights)
            self._load_error = None
            return True
        except Exception as exc:  # noqa: BLE001
            self._load_error = str(exc)[:240]
            self._model = None
            return False

    def _tracker(self, camera_id: str, *, pedestrian: bool = False) -> IoUTracker:
        store = self._ped_trackers if pedestrian else self._trackers
        if camera_id not in store:
            store[camera_id] = IoUTracker(
                iou_thresh=0.3,
                max_misses=5,
                confirm_hits=2,
            )
        return store[camera_id]

    def detect(self, image_path: Path, *, camera_id: str = "default") -> dict[str, Any]:
        """Detect + update tracks for one camera. Returns research analytics schema."""
        empty = {
            "ok": False,
            "is_vehicle_count": False,
            "visible_vehicle_tracks": None,
            "vehicle_flow_count": None,
            "vehicle_count": None,
            "occupancy_ratio": None,
            "queue_length_proxy_m": None,
            "pedestrian_count": None,
            "counts_by_class": {},
            "pedestrian_present": False,
            "infer_ms": None,
            "device": str(self._device),
            "source": self.SOURCE,
            "context_reliability": None,
            "reliability_components": {},
            "confidence": None,
            "error": None,
        }
        if not image_path.is_file():
            empty["error"] = "frame_missing"
            return empty
        if not self._ensure_model():
            empty["error"] = self._load_error or "model_unavailable"
            return empty

        t0 = time.perf_counter()
        try:
            results = self._model.predict(
                source=str(image_path),
                conf=self.conf,
                iou=self.iou,
                imgsz=self.imgsz,
                device=self._device,
                classes=[0, *_VEHICLE_CLASSES],
                max_det=self.max_det,
                verbose=False,
            )
        except Exception as exc:  # noqa: BLE001
            empty["error"] = str(exc)[:240]
            return empty

        ms = round((time.perf_counter() - t0) * 1000.0, 1)
        self._last_ms = ms
        r0 = results[0] if results else None

        veh_dets: list[tuple[tuple[float, float, float, float], int, float]] = []
        ped_dets: list[tuple[tuple[float, float, float, float], int]] = []
        h = w = 1
        confs: list[float] = []
        if r0 is not None:
            h, w = int(r0.orig_shape[0]), int(r0.orig_shape[1])
            if r0.boxes is not None and len(r0.boxes):
                xyxy = r0.boxes.xyxy.tolist()
                clss = r0.boxes.cls.tolist()
                conf_list = r0.boxes.conf.tolist() if r0.boxes.conf is not None else [0.5] * len(xyxy)
                for box, cls_id, score in zip(xyxy, clss, conf_list, strict=False):
                    cid = int(cls_id)
                    bb = (float(box[0]), float(box[1]), float(box[2]), float(box[3]))
                    sc = float(score)
                    if cid == 0:
                        ped_dets.append((bb, 0))
                    elif cid in _VEHICLE_CLASSES:
                        veh_dets.append((bb, cid, sc))
                        confs.append(sc)

        with self._lock:
            tr_engine = self._tracker(camera_id)
            veh_tracks = tr_engine.update([(b, c) for b, c, _s in veh_dets])
            ped_tracks = self._tracker(camera_id, pedestrian=True).update(ped_dets)
            active_all = list(tr_engine.tracks.values())
            confirmed_n = sum(1 for t in active_all if t.confirmed)
            track_confirm_ratio = (confirmed_n / len(active_all)) if active_all else 0.0

        zone_y = self.zone_y0 * h
        zone_area = max(1.0, float(w) * float(h - zone_y))
        occ_area = 0.0
        counts: dict[str, int] = {}
        use_tracks = veh_tracks if veh_tracks else []
        if not use_tracks and veh_dets:
            for bbox, cls_id, _sc in veh_dets:
                name = _CLASS_NAMES.get(cls_id, str(cls_id))
                counts[name] = counts.get(name, 0) + 1
                x1, y1, x2, y2 = bbox
                cy = 0.5 * (y1 + y2)
                if cy >= zone_y:
                    occ_area += max(0.0, (x2 - x1) * (y2 - y1))
            n = sum(counts.values())
            cold = True
        else:
            cold = False
            for tr in use_tracks:
                name = _CLASS_NAMES.get(tr.cls_id, str(tr.cls_id))
                counts[name] = counts.get(name, 0) + 1
                x1, y1, x2, y2 = tr.bbox
                cy = 0.5 * (y1 + y2)
                if cy >= zone_y:
                    occ_area += max(0.0, (x2 - x1) * (y2 - y1))
            n = len(use_tracks)

        occupancy = min(1.0, occ_area / zone_area)
        queue_m = round(occupancy * self.meters_per_norm_height, 1)
        ped_n = len(ped_tracks) if ped_tracks else len(ped_dets)
        band = "high" if n >= 25 or occupancy >= 0.55 else ("medium" if n >= 12 or occupancy >= 0.28 else "low")

        mean_det_conf = float(sum(confs) / len(confs)) if confs else 0.0
        # Heuristic composite — NOT a calibrated probability of correctness
        frame_fresh = 1.0
        scene_valid = 1.0 if 18.0 <= (float(getattr(r0, "orig_shape", [0])[0] or 1)) else 0.5
        # Use luma from prior estimate if present in path sidecar — approximate via mean conf presence
        model_health = 1.0 if self._model is not None else 0.0
        consecutive = 0.0 if cold else min(1.0, 0.35 + 0.65 * track_confirm_ratio)
        components = {
            "mean_detector_score": round(mean_det_conf, 3),
            "track_confirmation_ratio": round(float(track_confirm_ratio), 3),
            "frame_fresh": frame_fresh,
            "scene_valid": round(scene_valid, 3),
            "consecutive_track_support": round(consecutive, 3),
            "model_health": model_health,
            "cold_start": cold,
        }
        context_reliability = round(
            0.35 * mean_det_conf
            + 0.25 * track_confirm_ratio
            + 0.15 * frame_fresh
            + 0.10 * scene_valid
            + 0.10 * consecutive
            + 0.05 * model_health,
            3,
        )

        if self.annotate and r0 is not None:
            try:
                plotted = r0.plot()
                import cv2

                yz = int(zone_y)
                cv2.line(plotted, (0, yz), (w, yz), (80, 180, 255), 2)
                label = (
                    f"tracks={n} occ={occupancy:.2f} q≈{queue_m}m "
                    f"rel={context_reliability} {self.SOURCE}"
                )
                cv2.rectangle(plotted, (0, 0), (min(w, 720), 36), (20, 20, 20), -1)
                cv2.putText(
                    plotted,
                    label[:90],
                    (8, 24),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (240, 240, 240),
                    2,
                    cv2.LINE_AA,
                )
                for tr in use_tracks:
                    x1, y1, x2, y2 = map(int, tr.bbox)
                    cv2.putText(
                        plotted,
                        f"ID{tr.track_id}",
                        (x1, max(12, y1 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (50, 255, 50),
                        1,
                        cv2.LINE_AA,
                    )
                cv2.imwrite(str(image_path), plotted, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            except Exception:
                pass

        return {
            "ok": True,
            "is_vehicle_count": True,  # means tracks are detector-derived, not edge-energy
            "visible_vehicle_tracks": int(n),
            "vehicle_flow_count": None,  # reserved for line-crossing tracker
            "vehicle_count": int(n),  # deprecated alias → visible_vehicle_tracks
            "occupancy_ratio": round(float(occupancy), 3),
            "queue_length_proxy_m": queue_m,
            "queue_length_m_est": queue_m,
            "pedestrian_count": int(ped_n),
            "pedestrian_present": ped_n > 0,
            "counts_by_class": counts,
            "activity_band": band,
            "infer_ms": ms,
            "device": str(self._device),
            "source": self.SOURCE,
            "context_reliability": context_reliability,
            "reliability_components": components,
            "confidence": None,  # do not export fake probability
            "analytics_age_s": 0.0,
            "cold_start": cold,
            "note": (
                "visible_vehicle_tracks = confirmed IoU tracks in view (not veh/h). "
                "context_reliability is a heuristic composite, not calibrated accuracy. "
                "queue/occupancy are zone proxies."
            ),
        }
