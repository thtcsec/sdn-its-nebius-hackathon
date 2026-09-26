"""Lightweight multi-object IoU tracker (no plate / face ID).

Tracks boxes across successive frames so one vehicle is not counted
once per frame. Not ByteTrack-quality — good enough for occupancy proxy.
"""

from __future__ import annotations

from dataclasses import dataclass, field


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


@dataclass
class Track:
    track_id: int
    bbox: tuple[float, float, float, float]
    cls_id: int
    hits: int = 1
    misses: int = 0
    confirmed: bool = False


@dataclass
class IoUTracker:
    """Greedy IoU association with confirm-after-N-hits."""

    iou_thresh: float = 0.3
    max_misses: int = 4
    confirm_hits: int = 2
    _next_id: int = 1
    tracks: dict[int, Track] = field(default_factory=dict)

    def update(
        self, detections: list[tuple[tuple[float, float, float, float], int]]
    ) -> list[Track]:
        """detections: list of (xyxy, cls_id). Returns confirmed active tracks."""
        track_ids = list(self.tracks.keys())
        matched_t: set[int] = set()
        matched_d: set[int] = set()

        # Score matrix greedy
        pairs: list[tuple[float, int, int]] = []
        for ti, tid in enumerate(track_ids):
            for di, (bbox, _cls) in enumerate(detections):
                pairs.append((_iou(self.tracks[tid].bbox, bbox), ti, di))
        pairs.sort(reverse=True)
        for score, ti, di in pairs:
            if score < self.iou_thresh:
                break
            tid = track_ids[ti]
            if tid in matched_t or di in matched_d:
                continue
            bbox, cls_id = detections[di]
            tr = self.tracks[tid]
            tr.bbox = bbox
            tr.cls_id = cls_id
            tr.hits += 1
            tr.misses = 0
            if tr.hits >= self.confirm_hits:
                tr.confirmed = True
            matched_t.add(tid)
            matched_d.add(di)

        for _ti, tid in enumerate(track_ids):
            if tid in matched_t:
                continue
            tr = self.tracks[tid]
            tr.misses += 1
            if tr.misses > self.max_misses:
                del self.tracks[tid]

        for di, (bbox, cls_id) in enumerate(detections):
            if di in matched_d:
                continue
            tid = self._next_id
            self._next_id += 1
            self.tracks[tid] = Track(
                track_id=tid,
                bbox=bbox,
                cls_id=cls_id,
                hits=1,
                confirmed=self.confirm_hits <= 1,
            )

        return [t for t in self.tracks.values() if t.confirmed and t.misses == 0]
