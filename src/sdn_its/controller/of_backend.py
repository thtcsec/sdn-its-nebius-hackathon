"""OpenFlow push backends: mock / queue / ryu / http (WSL ovs-ofctl agent)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
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
        if action.upper() in {"INSTALL", "PUSH", "CREATE", "UPDATE", "ADD"}:
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
        if action.upper() in {"INSTALL", "PUSH", "CREATE", "UPDATE", "ADD"}:
            ok = ryu.push_flow(dpid, payload)
            print(f"[OpenFlow Ryu] push dpid={dpid} ok={ok}")
        else:
            ok = ryu.revoke_flow(dpid)
            print(f"[OpenFlow Ryu] revoke dpid={dpid} ok={ok}")

    _push.adapter = ryu  # type: ignore[attr-defined]
    return _push


def make_http_agent_backend(base_url: str | None = None) -> Callable:
    """Push flow-mods to WSL `scripts/wsl_of_agent.py` (ovs-ofctl on live Mininet bridges)."""
    url = (base_url or os.environ.get("OF_AGENT_URL") or "http://127.0.0.1:8089").rstrip("/")
    state: dict[str, Any] = {
        "backend": "http",
        "url": url,
        "connected": False,
        "flow_mods": 0,
        "last_mods": [],
        "datapaths": [],
    }

    def _get(path: str) -> dict[str, Any]:
        with urllib.request.urlopen(f"{url}{path}", timeout=2.0) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{url}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        health = _get("/health")
        state["connected"] = health.get("status") == "ok"
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        print(f"[OpenFlow HTTP] agent not reachable at {url}: {exc}")
        state["connected"] = False

    def _push(action: str, rule: FlowRule) -> None:
        payload = {
            "action": action,
            "rule_id": rule.rule_id,
            "dpid": rule.dpid,
            "src_ip": rule.src_ip,
            "of_action": rule.action,
            "priority": getattr(rule, "priority", 100),
            "idle_timeout": int(getattr(rule, "cooldown_seconds", 30) or 30),
        }
        try:
            result = _post("/flow_mod", payload)
            state["connected"] = True
            state["flow_mods"] = int(state["flow_mods"]) + 1
            mods = list(state["last_mods"])
            mods.append(result)
            state["last_mods"] = mods[-8:]
            print(f"[OpenFlow HTTP] {action} -> {result.get('bridge')} ok={result.get('ok')}")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            state["connected"] = False
            print(f"[OpenFlow HTTP] push failed: {exc}")

    _push.adapter = state  # type: ignore[attr-defined]
    return _push


def resolve_of_backend(mode: str | None = None) -> tuple[str, Callable]:
    """
    Resolve SDN_OF_BACKEND env (or explicit mode).

    - mock  : print-only (default Windows demo)
    - queue : in-memory OpenFlow mod log (lab dry-run without Mininet)
    - ryu   : RyuControllerAdapter (WSL2/Linux with live datapaths)
    - http / wsl / agent : HTTP → scripts/wsl_of_agent.py (ovs-ofctl)
    """
    chosen = (mode or os.environ.get("SDN_OF_BACKEND") or "mock").strip().lower()
    if chosen in {"queue", "log", "dry-run", "dryrun"}:
        return "queue", make_queue_backend()
    if chosen in {"ryu", "openflow", "of"}:
        return "ryu", make_ryu_backend()
    if chosen in {"http", "wsl", "agent", "ovs"}:
        return "http", make_http_agent_backend()
    return "mock", mock_openflow_push


def refresh_http_agent(adapter: dict[str, Any]) -> dict[str, Any]:
    """Pull live OVS dump from WSL of_agent into the http adapter state."""
    url = str(adapter.get("url") or "").rstrip("/")
    if not url:
        return {"ok": False, "error": "no agent url"}
    try:
        with urllib.request.urlopen(f"{url}/status", timeout=2.0) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        adapter["connected"] = True
        adapter["agent"] = payload
        bridges = payload.get("bridges") or {}
        adapter["datapaths"] = [br for br, info in bridges.items() if (info or {}).get("ok")]
        adapter["flow_mods"] = int(payload.get("flow_mods") or adapter.get("flow_mods") or 0)
        if payload.get("last_mods"):
            adapter["last_mods"] = list(payload["last_mods"])[-8:]
        return {"ok": True, "agent": payload}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        adapter["connected"] = False
        adapter["agent"] = {"error": str(exc)}
        return {"ok": False, "error": str(exc)}


def backend_status(callback: Callable, *, refresh: bool = False) -> dict[str, Any]:
    adapter = getattr(callback, "adapter", None)
    if adapter is None:
        return {"backend": "mock", "connected": False, "datapaths": [], "flow_mods": 0}
    if isinstance(adapter, dict):
        if refresh or adapter.get("backend") == "http":
            refresh_http_agent(adapter)
        agent = adapter.get("agent") or {}
        return {
            "backend": adapter.get("backend", "http"),
            "connected": bool(adapter.get("connected")),
            "datapaths": list(adapter.get("datapaths") or []),
            "flow_mods": int(adapter.get("flow_mods") or 0),
            "last_mods": list(adapter.get("last_mods") or [])[-5:],
            "url": adapter.get("url"),
            "bridges": agent.get("bridges") or {},
            "have_ovs_ofctl": agent.get("have_ovs_ofctl"),
            "agent_error": agent.get("error"),
        }
    return {
        "backend": "ryu" if adapter.connected and adapter.datapaths else "queue",
        "connected": bool(adapter.connected),
        "datapaths": list(adapter.datapaths.keys()),
        "flow_mods": len(adapter.flow_log),
        "last_mods": adapter.flow_log[-5:],
    }
