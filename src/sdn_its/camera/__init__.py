"""Camera-assisted physical context for safety-aware SDN mitigation.

Metadata-first: edge analytics publish traffic state; fusion joins SDN signals.
RTSP preview is optional and never the research claim.
"""

from .fusion import FusionEngine, FusionDecision
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
