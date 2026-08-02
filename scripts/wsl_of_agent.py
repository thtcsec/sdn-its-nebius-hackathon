#!/usr/bin/env python
"""Lightweight OpenFlow lab agent for WSL/Mininet (ovs-ofctl).

Runs inside WSL as root. Windows Flask API pushes mitigations here via HTTP
so the demo console drives *real* OVS flow tables without installing torch in WSL.

  sudo python scripts/wsl_of_agent.py --port 8089

Endpoints:
  GET  /health
  GET  /status
  POST /flow_mod   JSON: {action, dpid|bridge, src_ip, of_action, priority, idle_timeout}
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

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
    # Map trailing nibble / last non-zero digit → s1..s4
    try:
        n = int(s[-1], 16) if s else 1
    except ValueError:
        n = 1
    if n < 1 or n > 4:
        n = 1
    return f"s{n}"


def apply_flow_mod(payload: dict[str, Any]) -> dict[str, Any]:
    if shutil.which("ovs-ofctl") is None:
        return {"ok": False, "error": "ovs-ofctl not found (install openvswitch-switch)"}

    action = str(payload.get("action", "ADD")).upper()
    bridge = str(payload.get("bridge") or _bridge_from_dpid(payload.get("dpid")))
    src_ip = payload.get("src_ip")
    of_action = str(payload.get("of_action", "DROP")).upper()
    priority = int(payload.get("priority", 200))
    idle = int(payload.get("idle_timeout", 30) or 30)
    cookie = int(payload.get("cookie", abs(hash(str(payload.get("rule_id", "0")))) % 65000) or 1)

    entry = {
        "ts": time.time(),
        "action": action,
        "bridge": bridge,
        "src_ip": src_ip,
        "of_action": of_action,
        "priority": priority,
    }

    if action in {"DELETE", "REVOKE", "REMOVE", "DEL"}:
        if src_ip:
            cmd = ["ovs-ofctl", "del-flows", bridge, f"ip,nw_src={src_ip}"]
        else:
            cmd = ["ovs-ofctl", "del-flows", bridge, f"cookie={cookie}/-1"]
        code, out = _run(cmd)
        entry.update({"ok": code == 0, "cmd": cmd, "output": out.strip()[:500]})
        FLOW_LOG.append(entry)
        return entry

    # INSTALL / ADD / UPDATE
    if of_action in {"DROP", "DENY"}:
        actions = "drop"
    elif of_action in {"RATE_LIMIT", "THROTTLE_PACKET_IN", "THROTTLE"}:
        # Best-effort meter-less throttle: send to NORMAL with lower priority note
        actions = "normal"
        priority = max(10, priority // 2)
    else:
        actions = "normal"

    match = "ip"
    if src_ip:
        match = f"ip,nw_src={src_ip}"
    flow = f"cookie={cookie},priority={priority},idle_timeout={idle},{match},actions={actions}"
    cmd = ["ovs-ofctl", "add-flow", bridge, flow]
    code, out = _run(cmd)
    entry.update({"ok": code == 0, "cmd": cmd, "flow": flow, "output": out.strip()[:500]})
    FLOW_LOG.append(entry)
    return entry


def status_payload() -> dict[str, Any]:
    bridges = {}
    for br in BRIDGES:
        code, out = _run(["ovs-ofctl", "dump-flows", br])
        lines = [ln for ln in out.splitlines() if ln.strip() and not ln.startswith("NXST")]
        bridges[br] = {"ok": code == 0, "n_flows": len(lines), "sample": lines[:3]}
    return {
        "service": "wsl_of_agent",
        "uptime_seconds": round(time.time() - STARTED, 1),
        "have_ovs_ofctl": shutil.which("ovs-ofctl") is not None,
        "bridges": bridges,
        "flow_mods": len(FLOW_LOG),
        "last_mods": FLOW_LOG[-8:],
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
        path = urlparse(self.path).path
        if path in {"/", "/health"}:
            self._json(200, {"status": "ok", "service": "wsl_of_agent"})
            return
        if path == "/status":
            self._json(200, status_payload())
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
    print("[of_agent] POST /flow_mod  GET /status")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
