"""Mininet / V2X simulation package.

Heavy deps (torch) are imported lazily so topology can run in WSL without a full AI venv.
"""

from .topology import ITSEdgeTopology, create_its_topology

__all__ = [
    "ITSEdgeTopology",
    "create_its_topology",
    "LiveTrafficSimulator",
    "V2XTrafficGenerator",
]


def __getattr__(name: str):
    if name in {"LiveTrafficSimulator", "V2XTrafficGenerator"}:
        from .traffic_generator import LiveTrafficSimulator, V2XTrafficGenerator

        return {"LiveTrafficSimulator": LiveTrafficSimulator, "V2XTrafficGenerator": V2XTrafficGenerator}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
