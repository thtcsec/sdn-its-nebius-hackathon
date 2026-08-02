#!/usr/bin/env python
"""Lightweight OpenFlow lab agent for WSL/Mininet (ovs-ofctl).

Runs inside WSL as root. Windows Flask API pushes mitigations here via HTTP
so the demo console drives *real* OVS flow tables without installing torch in WSL.

  sudo python scripts/wsl_of_agent.py --port 8089

Endpoints:
  GET  /health
  GET  /status
  GET  /metrics
  GET  /verify?bridge=s1&src_ip=10.0.0.15&action=drop
  POST /flow_mod   JSON: {action, dpid|bridge, src_ip, of_action, priority, idle_timeout}
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

BRIDGES = ("s1", "s2", "s3", "s4")
FLOW_LOG: list[dict[str, Any]] = []
STARTED = time.time()


def _run(cmd: list[str], timeout: float = 5.0) -> tuple[int, str]:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=timeout)
        return 0, out
    except subprocess.CalledProcessError as exc:
        return exc.returncode, exc.output or str(exc)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)


def _bridge_from_dpid(dpid: str | None) -> str:
    if not dpid:
        return "s1"
    s = str(dpid).lower().replace(":", "").replace("0x", "")
    try:
        n = int(s[-1], 16) if s else 1
    except ValueError:
        n = 1
    if n < 1 or n > 4:
        n = 1
    return f"s{n}"


def dump_flows(bridge: str) -> tuple[bool, list[str]]:
    code, out = _run(["ovs-ofctl", "dump-flows", bridge])
    lines = [ln.strip() for ln in out.splitlines() if ln.strip() and not ln.startswith("NXST")]
    return code == 0, lines


def verify_flow(bridge: str, src_ip: str | None, want_action: str = "drop") -> dict[str, Any]:
    ok, lines = dump_flows(bridge)
    want = want_action.lower()
    matched = []
    for ln in lines:
        if src_ip and f"nw_src={src_ip}" not in ln:
            continue
        if want and want not in ln.lower():
            continue
        matched.append(ln)
    return {
        "ok": ok and bool(matched),
        "bridge": bridge,
        "src_ip": src_ip,
        "want_action": want,
        "verified_in_flow_dump": bool(matched),
        "matches": matched[:5],
        "n_flows": len(lines),
        "checked_at": time.time(),
    }


def port_stats(bridge: str = "s1") -> dict[str, Any]:
    code, out = _run(["ovs-ofctl", "dump-ports", bridge])
    # rx/tx pkts from "RX: ... pkts=N" lines
    rx = tx = None
    for ln in out.splitlines():
        m_rx = re.search(r"rx\s+pkts[=:]?\s*(\d+)", ln, re.I)
        m_tx = re.search(r"tx\s+pkts[=:]?\s*(\d+)", ln, re.I)
        if m_rx:
            rx = (rx or 0) + int(m_rx.group(1))
        if m_tx:
            tx = (tx or 0) + int(m_tx.group(1))
    return {"ok": code == 0, "bridge": bridge, "rx_pkts": rx, "tx_pkts": tx, "raw_head": out.splitlines()[:6]}


def apply_flow_mod(payload: dict[str, Any]) -> dict[str, Any]:
    if shutil.which("ovs-ofctl") is None:
        return {"ok": False, "error": "ovs-ofctl not found (install openvswitch-switch)"}

    t0 = time.perf_counter()
    action = str(payload.get("action", "ADD")).upper()
    bridge = str(payload.get("bridge") or _bridge_from_dpid(payload.get("dpid")))
    src_ip = payload.get("src_ip")
    of_action = str(payload.get("of_action", "DROP")).upper()
    priority = int(payload.get("priority", 200))
    # idle_timeout=0 means permanent (until DELETE)
    idle_raw = payload.get("idle_timeout", 30)
    idle = int(idle_raw) if idle_raw is not None else 30
    hard_raw = payload.get("hard_timeout", 0)
    hard = int(hard_raw) if hard_raw is not None else 0
    cookie = int(payload.get("cookie", abs(hash(str(payload.get("rule_id", "0")))) % 65000) or 1)
    rule_id = payload.get("rule_id")

    entry: dict[str, Any] = {
        "ts": time.time(),
        "requested_at": time.time(),
        "action": action,
        "bridge": bridge,
        "src_ip": src_ip,
        "of_action": of_action,
        "priority": priority,
        "cookie": cookie,
        "rule_id": rule_id,
        "idle_timeout": idle,
        "hard_timeout": hard,
    }

    if action in {"DELETE", "REVOKE", "REMOVE", "DEL"}:
        if src_ip:
            cmd = ["ovs-ofctl", "del-flows", bridge, f"ip,nw_src={src_ip}"]
        else:
            cmd = ["ovs-ofctl", "del-flows", bridge, f"cookie={cookie}/-1"]
        code, out = _run(cmd)
        entry.update(
            {
                "ok": code == 0,
                "cmd": cmd,
                "output": out.strip()[:500],
                "install_ms": round((time.perf_counter() - t0) * 1000.0, 3),
                "deleted_at": time.time(),
            }
        )
        FLOW_LOG.append(entry)
        return entry

    if of_action in {"DROP", "DENY"}:
        actions = "drop"
    elif of_action in {"RATE_LIMIT", "THROTTLE_PACKET_IN", "THROTTLE"}:
        actions = "normal"
        priority = max(10, priority // 2)
    else:
        actions = "normal"

    match = "ip"
    if src_ip:
        match = f"ip,nw_src={src_ip}"
    parts = [f"cookie={cookie}", f"priority={priority}"]
    if idle > 0:
        parts.append(f"idle_timeout={idle}")
    if hard > 0:
        parts.append(f"hard_timeout={hard}")
    parts.append(match)
    parts.append(f"actions={actions}")
    flow = ",".join(parts)
    cmd = ["ovs-ofctl", "add-flow", bridge, flow]
    code, out = _run(cmd)
    install_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    entry.update(
        {
            "ok": code == 0,
            "cmd": cmd,
            "flow": flow,
            "output": out.strip()[:500],
            "install_ms": install_ms,
            "installed_at": time.time() if code == 0 else None,
        }
    )
    # Verify in dump-flows
    ver = verify_flow(bridge, src_ip if src_ip else None, "drop" if actions == "drop" else actions)
    entry["verified_in_flow_dump"] = bool(ver.get("verified_in_flow_dump"))
    entry["switch_ack"] = bool(code == 0 and ver.get("verified_in_flow_dump"))
    entry["verify"] = ver
    FLOW_LOG.append(entry)
    return entry


def status_payload() -> dict[str, Any]:
    bridges = {}
    for br in BRIDGES:
        ok, lines = dump_flows(br)
        bridges[br] = {"ok": ok, "n_flows": len(lines), "sample": lines[:5]}
    return {
        "service": "wsl_of_agent",
        "uptime_seconds": round(time.time() - STARTED, 1),
        "have_ovs_ofctl": shutil.which("ovs-ofctl") is not None,
        "bridges": bridges,
        "flow_mods": len(FLOW_LOG),
        "last_mods": FLOW_LOG[-8:],
        "network_evidence": any((bridges.get(b) or {}).get("ok") for b in BRIDGES),
    }


def metrics_payload() -> dict[str, Any]:
    ports = {br: port_stats(br) for br in BRIDGES}
    last = FLOW_LOG[-1] if FLOW_LOG else None
    return {
        "ts": time.time(),
        "ports": ports,
        "last_mod": last,
        "flow_mods": len(FLOW_LOG),
        "note": "Port counters are OVS dataplane proxies; not controller PacketIn/s without Ryu.",
    }


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, payload: dict[str, Any]):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # quieter
        print(f"[of_agent] {self.address_string()} {fmt % args}")

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        if path in {"/", "/health"}:
            self._json(200, {"status": "ok", "service": "wsl_of_agent"})
            return
        if path == "/status":
            self._json(200, status_payload())
            return
        if path == "/metrics":
            self._json(200, metrics_payload())
            return
        if path == "/verify":
            bridge = (qs.get("bridge") or ["s1"])[0]
            src_ip = (qs.get("src_ip") or [None])[0]
            action = (qs.get("action") or ["drop"])[0]
            self._json(200, verify_flow(bridge, src_ip, action))
            return
        self._json(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid json"})
            return
        if path == "/flow_mod":
            self._json(200, apply_flow_mod(payload if isinstance(payload, dict) else {}))
            return
        self._json(404, {"error": "not found"})


def main():
    parser = argparse.ArgumentParser(description="WSL OVS OpenFlow lab agent")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8089)
    args = parser.parse_args()
    print(f"[of_agent] listening on http://{args.host}:{args.port}")
    print("[of_agent] POST /flow_mod  GET /status /metrics /verify")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
