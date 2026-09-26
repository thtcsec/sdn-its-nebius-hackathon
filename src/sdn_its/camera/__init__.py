"""Camera-assisted physical context for safety-aware SDN mitigation.

Metadata-first: edge analytics publish traffic state; fusion joins SDN signals.
RTSP → YOLOv8 vehicle count (CUDA) for fusion; edge-energy is fallback only.
Preview may show annotated boxes. Not a multi-object tracker / not a video wall.
"""

from .fusion import FusionDecision, FusionEngine
from .models import CameraCard, TrafficContext
from .store import CameraContextStore, get_camera_store

__all__ = [
    "CameraCard",
    "CameraContextStore",
    "FusionDecision",
    "FusionEngine",
    "TrafficContext",
    "get_camera_store",
]
