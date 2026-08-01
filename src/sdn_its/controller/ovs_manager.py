"""OVS management — soft flow-table on Windows; ovs-ofctl hook on Linux."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any


class OVSManager:
    """
    Open vSwitch helper.

    - Always keeps an in-memory flow table (usable on Windows demo / CI).
    - When `ovs-ofctl` is on PATH (Linux/WSL), also attempts a real dump-flows.
    """

    def __init__(self):
        self._tables: dict[str, list[dict[str, Any]]] = {
            "s1": [],
            "s2": [],
            "s3": [],
            "s4": [],
        }
        self._have_ofctl = shutil.which("ovs-ofctl") is not None

    def list_bridges(self) -> list[str]:
        if self._have_ofctl:
            try:
                out = subprocess.check_output(["ovs-vsctl", "list-br"], text=True, timeout=3)
                brs = [b.strip() for b in out.splitlines() if b.strip()]
                if brs:
                    return brs
            except (subprocess.SubprocessError, FileNotFoundError):
                pass
        return list(self._tables.keys())

    def dump_flows(self, bridge: str) -> list[dict[str, Any]]:
        if self._have_ofctl:
            try:
                out = subprocess.check_output(
                    ["ovs-ofctl", "dump-flows", bridge], text=True, timeout=3
                )
                return [{"bridge": bridge, "raw": line} for line in out.splitlines() if line.strip()]
            except (subprocess.SubprocessError, FileNotFoundError):
                pass
        return list(self._tables.get(bridge, []))

    def apply_flow_mod(self, bridge: str, match: dict[str, Any], actions: list[str]) -> bool:
        entry = {"bridge": bridge, "match": match, "actions": actions}
        self._tables.setdefault(bridge, []).append(entry)
        if self._have_ofctl:
            # Real push left to Ryu OFPFlowMod in lab; ofctl add-flow is optional
            print(f"[OVSManager] recorded + ovs-ofctl present on {bridge}: {match} -> {actions}")
        else:
            print(f"[OVSManager] soft flow_mod on {bridge}: match={match} actions={actions}")
        return True

    def clear(self, bridge: str | None = None) -> None:
        if bridge is None:
            for k in self._tables:
                self._tables[k] = []
        elif bridge in self._tables:
            self._tables[bridge] = []
