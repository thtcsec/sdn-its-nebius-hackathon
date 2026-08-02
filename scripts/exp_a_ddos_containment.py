#!/usr/bin/env python3
"""Experiment A — DDoS containment with network evidence (Mininet / OVS).

Compares three arms on the ITS edge topology:

  none        — no mitigation
  permanent   — DROP attacker (idle_timeout=0) until explicit delete
  temporary   — DROP + short hard_timeout, then measure recovery

Measures (data-plane proxies — honest labels):
  legit_delivery_ratio   veh1 → tmc ping success
  attack_delivery_ratio  veh5 (10.0.0.15) → tmc ping success
  install_ms             ovs-ofctl add-flow → verified in dump-flows
  recovery_ms            rule gone → legit still OK / attack restored

Run inside WSL/Linux as root (needs Mininet + OVS):

  sudo python3 scripts/exp_a_ddos_containment.py
  sudo python3 scripts/exp_a_ddos_containment.py --dry-run   # schema only (Windows CI)

Writes:
  experiments/exp02_ddos/results/exp_a_metrics.json
  artifacts/results/exp_a/exp_a_metrics.json  (if artifacts tree exists)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

ATTACKER_IP = "10.0.0.15"
LEGIT_IP = "10.0.0.11"
TMC_IP = "10.0.0.1"
BRIDGE = "s1"
PING_COUNT = 20


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(cmd: list[str], timeout: float = 10.0) -> tuple[int, str]:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=timeout)
        return 0, out
    except subprocess.CalledProcessError as exc:
        return exc.returncode, exc.output or str(exc)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)


def ofctl_add_drop(src_ip: str, *, idle: int = 0, hard: int = 0, priority: int = 200) -> dict[str, Any]:
    t0 = time.perf_counter()
    parts = [f"priority={priority}"]
    if idle > 0:
        parts.append(f"idle_timeout={idle}")
    if hard > 0:
        parts.append(f"hard_timeout={hard}")
    parts.append(f"ip,nw_src={src_ip}")
    parts.append("actions=drop")
    flow = ",".join(parts)
    code, out = _run(["ovs-ofctl", "add-flow", BRIDGE, flow])
    install_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    verified = False
    dump = ""
    if code == 0:
        # brief settle + verify
        time.sleep(0.05)
        _, dump = _run(["ovs-ofctl", "dump-flows", BRIDGE])
        verified = f"nw_src={src_ip}" in dump and "drop" in dump.lower()
    return {
        "ok": code == 0 and verified,
        "flow": flow,
        "install_ms": install_ms,
        "verified_in_flow_dump": verified,
        "switch_ack": code == 0 and verified,
        "dump_sample": "\n".join(dump.splitlines()[:6]),
        "output": out.strip()[:300],
        "installed_at": time.time() if code == 0 else None,
    }


def ofctl_del_attacker(src_ip: str = ATTACKER_IP) -> dict[str, Any]:
    t0 = time.perf_counter()
    code, out = _run(["ovs-ofctl", "del-flows", BRIDGE, f"ip,nw_src={src_ip}"])
    return {
        "ok": code == 0,
        "delete_ms": round((time.perf_counter() - t0) * 1000.0, 3),
        "output": out.strip()[:300],
        "deleted_at": time.time(),
    }


def host_ping(net, src_name: str, dst_ip: str, count: int = PING_COUNT) -> dict[str, Any]:
    """Return delivery ratio from Mininet host ping."""
    h = net.get(src_name)
    t0 = time.perf_counter()
    # -W 1: 1s deadline per probe; -c count
    raw = h.cmd(f"ping -c {count} -W 1 {dst_ip}")
    elapsed = time.perf_counter() - t0
    received = 0
    transmitted = count
    m = re.search(r"(\d+)\s+packets transmitted,\s+(\d+)\s+received", raw)
    if m:
        transmitted = int(m.group(1))
        received = int(m.group(2))
    else:
        # fallback: count "bytes from"
        received = len(re.findall(r"bytes from", raw))
    rtt = None
    m_rtt = re.search(r"rtt min/avg/max/[^=]+=\s*([\d.]+)/([\d.]+)/([\d.]+)", raw)
    if m_rtt:
        rtt = float(m_rtt.group(2))
    ratio = (received / transmitted) if transmitted else 0.0
    return {
        "src": src_name,
        "dst": dst_ip,
        "transmitted": transmitted,
        "received": received,
        "delivery_ratio": round(ratio, 4),
        "rtt_avg_ms": rtt,
        "wall_s": round(elapsed, 3),
        "raw_tail": "\n".join(raw.strip().splitlines()[-4:]),
    }


def measure_pair(net) -> dict[str, Any]:
    legit = host_ping(net, "veh1", TMC_IP)
    attack = host_ping(net, "veh5", TMC_IP)
    return {
        "legit_delivery_ratio": legit["delivery_ratio"],
        "attack_delivery_ratio": attack["delivery_ratio"],
        "legit_rtt_avg_ms": legit["rtt_avg_ms"],
        "attack_rtt_avg_ms": attack["rtt_avg_ms"],
        "legit": legit,
        "attack": attack,
        # Honest proxy names (not PacketIn/s without Ryu)
        "packetin_per_s": None,
        "packetin_note": "Not measured — of_agent path has no PacketIn counter; use Ryu for PacketIn/s.",
    }


def run_arm_none(net) -> dict[str, Any]:
    traffic = measure_pair(net)
    return {
        "arm": "none",
        "description": "No mitigation",
        "actuation": {"requested": False, "switch_ack": False, "verified_in_flow_dump": False},
        "traffic": traffic,
        "outcome": {
            "attack_reduction_pct": 0.0,
            "legitimate_delivery_ratio": traffic["legit_delivery_ratio"],
            "sla_violation": traffic["legit_delivery_ratio"] < 0.8,
            "rollback_success": None,
            "recovery_ms": None,
            "install_ms": None,
        },
    }


def run_arm_permanent(net, baseline_attack: float) -> dict[str, Any]:
    install = ofctl_add_drop(ATTACKER_IP, idle=0, hard=0)
    time.sleep(0.2)
    traffic = measure_pair(net)
    # cleanup so next arm starts clean
    ofctl_del_attacker()
    time.sleep(0.2)
    reduction = None
    if baseline_attack and baseline_attack > 0:
        reduction = round(max(0.0, (baseline_attack - traffic["attack_delivery_ratio"]) / baseline_attack) * 100.0, 2)
    return {
        "arm": "permanent",
        "description": "Permanent DROP (idle_timeout=0) on attacker src",
        "actuation": {
            "requested": True,
            "rule": install.get("flow"),
            "switch_ack": install.get("switch_ack"),
            "verified_in_flow_dump": install.get("verified_in_flow_dump"),
            "install_ms": install.get("install_ms"),
            "dump_sample": install.get("dump_sample"),
        },
        "traffic": traffic,
        "outcome": {
            "attack_reduction_pct": reduction,
            "legitimate_delivery_ratio": traffic["legit_delivery_ratio"],
            "sla_violation": traffic["legit_delivery_ratio"] < 0.8,
            "rollback_success": None,
            "recovery_ms": None,
            "install_ms": install.get("install_ms"),
        },
    }


def run_arm_temporary(net, baseline_attack: float, hard_timeout: int = 8) -> dict[str, Any]:
    # Do NOT use short hard_timeout for the measure window — ping arms take ~PING_COUNT seconds
    # each, so hard_timeout=8 would expire mid-measurement. Temporary = install DROP, measure,
    # then explicit DELETE (models cooldown rollback). hard_timeout kept in metadata only.
    install = ofctl_add_drop(ATTACKER_IP, idle=0, hard=0)
    time.sleep(0.2)
    # Attack first while rule is guaranteed present
    attack_during = host_ping(net, "veh5", TMC_IP)
    legit_during = host_ping(net, "veh1", TMC_IP)
    during = {
        "legit_delivery_ratio": legit_during["delivery_ratio"],
        "attack_delivery_ratio": attack_during["delivery_ratio"],
        "legit_rtt_avg_ms": legit_during["rtt_avg_ms"],
        "attack_rtt_avg_ms": attack_during["rtt_avg_ms"],
        "legit": legit_during,
        "attack": attack_during,
        "packetin_per_s": None,
        "packetin_note": "Not measured — of_agent path has no PacketIn counter; use Ryu for PacketIn/s.",
    }
    t_wait0 = time.perf_counter()
    deleted = ofctl_del_attacker()
    recovered_dump = False
    for _ in range(40):
        _, dump = _run(["ovs-ofctl", "dump-flows", BRIDGE])
        if f"nw_src={ATTACKER_IP}" not in dump or "drop" not in dump.lower():
            recovered_dump = True
            break
        time.sleep(0.1)
    recovery_ms = round((time.perf_counter() - t_wait0) * 1000.0, 3)
    after = measure_pair(net)
    reduction = None
    if baseline_attack and baseline_attack > 0:
        reduction = round(max(0.0, (baseline_attack - during["attack_delivery_ratio"]) / baseline_attack) * 100.0, 2)
    return {
        "arm": "temporary",
        "description": (
            "Temporary DROP + explicit rollback DELETE "
            f"(cooldown model; hard_timeout param={hard_timeout}s unused for measure window)"
        ),
        "actuation": {
            "requested": True,
            "rule": install.get("flow"),
            "switch_ack": install.get("switch_ack"),
            "verified_in_flow_dump": install.get("verified_in_flow_dump"),
            "install_ms": install.get("install_ms"),
            "dump_sample": install.get("dump_sample"),
            "delete_ok": deleted.get("ok"),
            "rule_cleared_from_dump": recovered_dump,
        },
        "traffic": {"during": during, "after_rollback": after},
        "outcome": {
            "attack_reduction_pct": reduction,
            "legitimate_delivery_ratio": during["legit_delivery_ratio"],
            "legit_after_rollback": after["legit_delivery_ratio"],
            "attack_after_rollback": after["attack_delivery_ratio"],
            "sla_violation": during["legit_delivery_ratio"] < 0.8,
            "rollback_success": bool(
                deleted.get("ok")
                and recovered_dump
                and after["legit_delivery_ratio"] >= 0.8
                and after["attack_delivery_ratio"] >= 0.8
            ),
            "recovery_ms": recovery_ms,
            "install_ms": install.get("install_ms"),
        },
    }


def dry_run_payload() -> dict[str, Any]:
    return {
        "experiment": "A",
        "title": "DDoS containment — reversible mitigation",
        "generated_at": _utc(),
        "network_evidence": False,
        "dry_run": True,
        "note": "Schema-only. Run on WSL/Linux with Mininet+OVS for real numbers.",
        "arms": [
            {
                "arm": "none",
                "outcome": {"attack_reduction_pct": None, "legitimate_delivery_ratio": None},
            },
            {
                "arm": "permanent",
                "outcome": {"attack_reduction_pct": None, "legitimate_delivery_ratio": None, "install_ms": None},
            },
            {
                "arm": "temporary",
                "outcome": {
                    "attack_reduction_pct": None,
                    "legitimate_delivery_ratio": None,
                    "rollback_success": None,
                    "recovery_ms": None,
                    "install_ms": None,
                },
            },
        ],
        "summary": {
            "pass_criteria": {
                "permanent_cuts_attack": "attack_delivery_ratio(permanent) << attack_delivery_ratio(none)",
                "temporary_preserves_legit": "legit_delivery_ratio(temporary) >= 0.8",
                "rollback_restores": "rollback_success == true",
            }
        },
    }


def write_results(payload: dict[str, Any]) -> list[Path]:
    paths = [
        ROOT / "experiments" / "exp02_ddos" / "results" / "exp_a_metrics.json",
        ROOT / "artifacts" / "results" / "exp_a" / "exp_a_metrics.json",
    ]
    written = []
    for p in paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        written.append(p)
    return written


def run_live(hard_timeout: int) -> dict[str, Any]:
    try:
        from mininet.link import TCLink
        from mininet.log import setLogLevel
        from mininet.net import Mininet
        from mininet.node import OVSKernelSwitch
    except ImportError as exc:
        raise SystemExit(
            f"Mininet not available ({exc}). Use WSL: sudo python3 scripts/exp_a_ddos_containment.py"
        ) from exc

    from sdn_its.simulation.topology import ITSEdgeTopology

    setLogLevel("info")
    # Clean leftover
    subprocess.call(["mn", "-c"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if shutil.which("service"):
        subprocess.call(["service", "openvswitch-switch", "start"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    topo = ITSEdgeTopology()
    net = Mininet(topo=topo, controller=None, link=TCLink, switch=OVSKernelSwitch)
    net.start()
    # Ensure learning / forwarding without controller
    for sw in net.switches:
        sw.cmd("ovs-vsctl set-fail-mode", sw.name, "standalone")
        sw.cmd("ovs-vsctl set Bridge", sw.name, "other-config:disable-in-band=true")

    time.sleep(1.0)
    # Warm ARP
    net.get("veh1").cmd(f"ping -c 2 -W 1 {TMC_IP}")
    net.get("veh5").cmd(f"ping -c 2 -W 1 {TMC_IP}")
    time.sleep(0.5)

    arms: list[dict[str, Any]] = []
    none = run_arm_none(net)
    arms.append(none)
    baseline_attack = float(none["traffic"]["attack_delivery_ratio"] or 0.0)
    arms.append(run_arm_permanent(net, baseline_attack))
    arms.append(run_arm_temporary(net, baseline_attack, hard_timeout=hard_timeout))

    net.stop()
    subprocess.call(["mn", "-c"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    perm = next(a for a in arms if a["arm"] == "permanent")
    temp = next(a for a in arms if a["arm"] == "temporary")
    summary = {
        "network_evidence": True,
        "permanent_verified": bool(perm["actuation"].get("verified_in_flow_dump")),
        "temporary_verified": bool(temp["actuation"].get("verified_in_flow_dump")),
        "permanent_attack_reduction_pct": perm["outcome"].get("attack_reduction_pct"),
        "temporary_attack_reduction_pct": temp["outcome"].get("attack_reduction_pct"),
        "temporary_rollback_success": temp["outcome"].get("rollback_success"),
        "temporary_recovery_ms": temp["outcome"].get("recovery_ms"),
        "legit_none": none["traffic"]["legit_delivery_ratio"],
        "legit_during_temporary": temp["outcome"].get("legitimate_delivery_ratio"),
        "caveats": [
            "Metrics are ICMP delivery ratios (data-plane), not controller PacketIn/s.",
            "Attacker is veh5=10.0.0.15; legitimate is veh1=10.0.0.11 → tmc=10.0.0.1.",
            "THROTTLE_PACKET_IN is not exercised here (needs Ryu PacketIn path).",
        ],
    }
    return {
        "experiment": "A",
        "title": "DDoS containment — reversible mitigation",
        "generated_at": _utc(),
        "network_evidence": True,
        "dry_run": False,
        "topology": "ITSEdgeTopology",
        "attacker_ip": ATTACKER_IP,
        "legit_ip": LEGIT_IP,
        "tmc_ip": TMC_IP,
        "ping_count": PING_COUNT,
        "arms": arms,
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Experiment A — DDoS containment")
    parser.add_argument("--dry-run", action="store_true", help="Write schema-only JSON (no Mininet)")
    parser.add_argument("--hard-timeout", type=int, default=8, help="Temporary DROP hard_timeout seconds")
    args = parser.parse_args()

    if args.dry_run or os.name == "nt":
        if os.name == "nt" and not args.dry_run:
            print("[exp_a] Windows detected — writing dry-run schema. Use WSL for live run.")
        payload = dry_run_payload()
    else:
        if os.geteuid() != 0:
            print("[exp_a] WARNING: Mininet usually needs root. Continuing anyway…")
        payload = run_live(hard_timeout=args.hard_timeout)

    written = write_results(payload)
    print(json.dumps({"wrote": [str(p) for p in written], "network_evidence": payload.get("network_evidence"), "summary": payload.get("summary")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
