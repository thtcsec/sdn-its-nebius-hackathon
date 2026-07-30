"""OVS management stub — roadmap hook for real OpenFlow / ovs-vsctl integration."""

from __future__ import annotations

from typing import Any


class OVSManager:
    """
    Placeholder for Open vSwitch flow-table inspection and management.

    Production deployments should replace mock methods with ovs-ofctl / OVSDB calls.
    """

    def list_bridges(self) -> list[str]:
        return ["s1", "s2", "s3", "s4"]

    def dump_flows(self, bridge: str) -> list[dict[str, Any]]:
        return [{"bridge": bridge, "flows": [], "note": "stub — connect ovs-ofctl"}]

    def apply_flow_mod(self, bridge: str, match: dict[str, Any], actions: list[str]) -> bool:
        print(f"[OVSManager stub] flow_mod on {bridge}: match={match} actions={actions}")
        return True
