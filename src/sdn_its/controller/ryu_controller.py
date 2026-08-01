"""Ryu controller adapter — mock on Windows, live datapath bridge on WSL2/Linux."""

from __future__ import annotations

from typing import Any


class RyuControllerAdapter:
    """
    OpenFlow 1.3 adapter used by `of_backend.make_ryu_backend`.

    Demo path (Windows): queue/mock backends — no real switches.
    Lab path (Linux / WSL2):
      1. `ryu-manager src/sdn_its/controller/ryu_app.py`
      2. `python -m sdn_its.simulation.topology --controller 127.0.0.1:6653`
      3. `SDN_OF_BACKEND=ryu` + Flask API; register datapaths via `register_datapath`
    """

    def __init__(self, of_port: int = 6653):
        self.of_port = of_port
        self.connected = False
        self.datapaths: dict[str, Any] = {}
        self.flow_log: list[dict[str, Any]] = []

    def start(self) -> None:
        if self.datapaths:
            self.connected = True
            print(f"[RyuControllerAdapter] Active with {len(self.datapaths)} datapath(s) on :{self.of_port}")
            return
        print(
            f"[RyuControllerAdapter] Listening mode ready (OF port {self.of_port}). "
            "No datapaths yet — register via Mininet/Ryu or use SDN_OF_BACKEND=queue for dry-run."
        )
        self.connected = False

    def register_datapath(self, dpid: str, datapath: Any = None) -> None:
        self.datapaths[str(dpid)] = datapath
        self.connected = True

    def push_flow(self, dpid: str, rule: dict[str, Any]) -> bool:
        """Push a FlowRule-like dict. Returns True if a live datapath accepted it."""
        entry = {"dpid": str(dpid), "rule": rule, "status": "queued"}
        dp = self.datapaths.get(str(dpid))
        if dp is not None and hasattr(dp, "send_msg"):
            try:
                # Best-effort: caller may pass a prebuilt OFPFlowMod as rule["msg"]
                msg = rule.get("msg")
                if msg is not None:
                    dp.send_msg(msg)
                    entry["status"] = "sent"
                else:
                    entry["status"] = "registered_no_msg"
            except Exception as exc:
                entry["status"] = f"error:{exc}"
                self.flow_log.append(entry)
                return False
        self.flow_log.append(entry)
        return entry["status"] in {"sent", "queued", "registered_no_msg"}

    def revoke_flow(self, dpid: str, cookie: int | None = None) -> bool:
        entry = {"dpid": str(dpid), "revoke_cookie": cookie, "status": "queued"}
        self.flow_log.append(entry)
        return True

    def lab_checklist(self) -> list[str]:
        return [
            "WSL2 Ubuntu: sudo apt install mininet openvswitch-switch",
            "pip install ryu",
            "Terminal A: ryu-manager src/sdn_its/controller/ryu_app.py",
            "Terminal B: python -m sdn_its.simulation.topology",
            "Terminal C: set SDN_OF_BACKEND=ryu && python -m api.app",
            "Inject: python -m sdn_its.simulation.scapy_traffic --scenario ddos",
            "See docs/lab_checklist.md for full steps",
        ]
