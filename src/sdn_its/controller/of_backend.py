"""OpenFlow push backends: mock (Windows demo), queue (lab dry-run), ryu (WSL/Linux)."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from sdn_its.controller.ryu_controller import RyuControllerAdapter
from sdn_its.mitigation.containment import FlowRule


def mock_openflow_push(action: str, rule: FlowRule) -> None:
    print(
        f"[OpenFlow Switch Channel] {action} Rule [{rule.rule_id}] -> "
        f"DPID={rule.dpid}, Match={rule.src_ip}, Action={rule.action}"
    )


def make_queue_backend(adapter: RyuControllerAdapter | None = None) -> Callable:
    """Record flow-mods in-memory (no Ryu). Useful for CI / Windows dry-run of OF path."""
    ryu = adapter or RyuControllerAdapter()
    ryu.connected = True

    def _push(action: str, rule: FlowRule) -> None:
        payload = {
            "action": action,
            "rule_id": rule.rule_id,
            "dpid": rule.dpid,
            "src_ip": rule.src_ip,
            "of_action": rule.action,
            "priority": getattr(rule, "priority", 100),
        }
        if action.upper() in {"INSTALL", "PUSH", "CREATE", "UPDATE"}:
            ryu.push_flow(str(rule.dpid), payload)
        else:
            ryu.revoke_flow(str(rule.dpid), cookie=None)
        print(f"[OpenFlow Queue] {action} logged ({len(ryu.flow_log)} mods)")

    _push.adapter = ryu  # type: ignore[attr-defined]
    return _push


def make_ryu_backend(of_port: int = 6653) -> Callable:
    """Bridge FlowRuleManager → RyuControllerAdapter (real OF when Ryu datapaths exist)."""
    ryu = RyuControllerAdapter(of_port=of_port)
    ryu.start()

    def _push(action: str, rule: FlowRule) -> None:
        payload = {
            "action": action,
            "rule_id": rule.rule_id,
            "src_ip": rule.src_ip,
            "dst_ip": getattr(rule, "dst_ip", None),
            "of_action": rule.action,
            "priority": getattr(rule, "priority", 100),
            "idle_timeout": int(getattr(rule, "cooldown_seconds", 30) or 30),
        }
        dpid = str(rule.dpid)
        if action.upper() in {"INSTALL", "PUSH", "CREATE", "UPDATE"}:
            ok = ryu.push_flow(dpid, payload)
            print(f"[OpenFlow Ryu] push dpid={dpid} ok={ok}")
        else:
            ok = ryu.revoke_flow(dpid)
            print(f"[OpenFlow Ryu] revoke dpid={dpid} ok={ok}")

    _push.adapter = ryu  # type: ignore[attr-defined]
    return _push


def resolve_of_backend(mode: str | None = None) -> tuple[str, Callable]:
    """
    Resolve SDN_OF_BACKEND env (or explicit mode).

    - mock  : print-only (default Windows demo)
    - queue : in-memory OpenFlow mod log (lab dry-run without Mininet)
    - ryu   : RyuControllerAdapter (WSL2/Linux with live datapaths)
    """
    chosen = (mode or os.environ.get("SDN_OF_BACKEND") or "mock").strip().lower()
    if chosen in {"queue", "log", "dry-run", "dryrun"}:
        return "queue", make_queue_backend()
    if chosen in {"ryu", "openflow", "of"}:
        return "ryu", make_ryu_backend()
    return "mock", mock_openflow_push


def backend_status(callback: Callable) -> dict[str, Any]:
    adapter = getattr(callback, "adapter", None)
    if adapter is None:
        return {"backend": "mock", "connected": False, "datapaths": [], "flow_mods": 0}
    return {
        "backend": "ryu" if adapter.connected and adapter.datapaths else "queue",
        "connected": bool(adapter.connected),
        "datapaths": list(adapter.datapaths.keys()),
        "flow_mods": len(adapter.flow_log),
        "last_mods": adapter.flow_log[-5:],
    }
