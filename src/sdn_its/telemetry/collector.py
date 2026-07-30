"""Telemetry collector stub for OVS / sFlow / OpenFlow stats push."""

from __future__ import annotations

import time
from typing import Any


class TelemetryCollector:
    """Collects flow-level counters from switches (mock / synthetic for demo)."""

    def __init__(self, poll_interval_ms: float = 5.0):
        self.poll_interval_ms = poll_interval_ms
        self._last_poll = 0.0

    def poll(self, dpid: str = "0000000000000001") -> dict[str, Any]:
        self._last_poll = time.time()
        return {
            "dpid": dpid,
            "timestamp": self._last_poll,
            "packet_rate": 0.0,
            "byte_rate": 0.0,
            "packet_in_count": 0,
            "note": "stub collector — wire to ovs-ofctl / sFlow in lab deployments",
        }

    def poll_batch(self, dpids: list[str] | None = None) -> list[dict[str, Any]]:
        dpids = dpids or ["0000000000000001", "0000000000000002"]
        return [self.poll(d) for d in dpids]
