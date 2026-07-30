"""Ryu controller stub — roadmap hook for real OpenFlow 1.3 Ryu app."""

from __future__ import annotations

from typing import Any


class RyuControllerAdapter:
    """
    Documented stub for a Ryu OpenFlow application.

    Demo path (Windows): Flask REST API + mock OpenFlow push callback.
    Lab path (Linux / WSL2):
      1. Install Ryu + Mininet-WiFi
      2. Launch topology from `src/sdn_its/simulation/topology.py`
      3. Bridge `FlowRuleManager.of_push_callback` → `push_flow` → OFPFlowMod
    """

    def __init__(self, of_port: int = 6653):
        self.of_port = of_port
        self.connected = False
        self.datapaths: dict[str, Any] = {}
        self.flow_log: list[dict[str, Any]] = []

    def start(self) -> None:
        print(
            f"[RyuControllerAdapter stub] Would listen on OpenFlow port {self.of_port}. "
            "Use REST API demo on Windows; deploy Ryu+Mininet on Linux/WSL2 for real switches."
        )
        self.connected = False

    def register_datapath(self, dpid: str, datapath: Any = None) -> None:
        self.datapaths[dpid] = datapath
        self.connected = True

    def push_flow(self, dpid: str, rule: dict[str, Any]) -> bool:
        self.flow_log.append({"dpid": dpid, "rule": rule})
        print(f"[RyuControllerAdapter stub] push_flow dpid={dpid} rule={rule}")
        return False

    def revoke_flow(self, dpid: str, cookie: int | None = None) -> bool:
        print(f"[RyuControllerAdapter stub] revoke_flow dpid={dpid} cookie={cookie}")
        return False

    def lab_checklist(self) -> list[str]:
        return [
            "Install Ryu + Mininet-WiFi on Ubuntu/WSL2",
            "Start controller listening OF 1.3",
            "Launch topology: python -m sdn_its.simulation.topology",
            "Point FlowRuleManager.of_push_callback → RyuControllerAdapter.push_flow",
            "Validate packet_in flood / LOFT with Scapy generators",
        ]
