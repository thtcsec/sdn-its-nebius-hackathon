"""
topology.py - Mininet & Mininet-WiFi Custom Network Topology for ITS Edge Network

Creates an Intelligent Transportation System (ITS) Edge Topology comprising:
- Remote SDN Controller (Ryu / ONOS)
- Roadside Units (RSU / AP Switches: s1, s2, s3, s4)
- V2X Stations / Connected Vehicles (veh1..veh6)
- RSU Edge Compute Nodes & Traffic Management Center (TMC)

Compatible with Mininet & Mininet-WiFi emulation environments on Linux/WSL2.
Includes a fallback dry-run topology simulator for cross-platform validation.
"""

import argparse

# Mininet / Mininet-WiFi imports (wrapped with graceful fallback for non-Linux platforms)
try:
    from mininet.cli import CLI
    from mininet.link import TCLink
    from mininet.net import Mininet
    from mininet.node import OVSKernelSwitch, RemoteController
    from mininet.topo import Topo
    MININET_AVAILABLE = True
except ImportError:
    MININET_AVAILABLE = False
    Topo = object  # Base class fallback for Windows development


class ITSEdgeTopology(Topo):
    """
    Custom Mininet Topology for V2X Edge Network.

    Structure:
    - 4 RSU/OVS Switches (s1: Core RSU, s2: West AP, s3: East AP, s4: Highway Edge)
    - 1 Traffic Management Center (TMC) Server
    - 2 RSU Edge Nodes (edge_rsu1, edge_rsu2)
    - 6 Connected Vehicles (veh1..veh6)
    """
    def build(self, **kwargs):
        if not MININET_AVAILABLE:
            return

        print("[*] Building Mininet ITS Edge Network Topology...")

        # 1. Add Open vSwitch (OVS) Roadside Units / Access Points
        s1 = self.addSwitch('s1', dpid='0000000000000001', cls=OVSKernelSwitch)  # Core Intersection RSU
        s2 = self.addSwitch('s2', dpid='0000000000000002', cls=OVSKernelSwitch)  # West Intersection RSU
        s3 = self.addSwitch('s3', dpid='0000000000000003', cls=OVSKernelSwitch)  # East Intersection RSU
        s4 = self.addSwitch('s4', dpid='0000000000000004', cls=OVSKernelSwitch)  # Highway Gateway RSU

        # 2. Add Infrastructure Servers & Edge Computing Nodes
        tmc = self.addHost('tmc', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
        edge1 = self.addHost('edge1', ip='10.0.0.2/24', mac='00:00:00:00:00:02')
        edge2 = self.addHost('edge2', ip='10.0.0.3/24', mac='00:00:00:00:00:03')

        # 3. Add V2X Vehicles
        veh1 = self.addHost('veh1', ip='10.0.0.11/24', mac='00:00:00:00:00:11')
        veh2 = self.addHost('veh2', ip='10.0.0.12/24', mac='00:00:00:00:00:12')
        veh3 = self.addHost('veh3', ip='10.0.0.13/24', mac='00:00:00:00:00:13')
        veh4 = self.addHost('veh4', ip='10.0.0.14/24', mac='00:00:00:00:00:14')
        veh5 = self.addHost('veh5', ip='10.0.0.15/24', mac='00:00:00:00:00:15')  # Malicious/Suspicious Vehicle
        veh6 = self.addHost('veh6', ip='10.0.0.16/24', mac='00:00:00:00:00:16')

        # 4. Inter-Switch Links (Fibre Backhaul: 100Mbps, 2ms delay)
        self.addLink(s1, s2, bw=100, delay='2ms', loss=0, cls=TCLink)
        self.addLink(s1, s3, bw=100, delay='2ms', loss=0, cls=TCLink)
        self.addLink(s1, s4, bw=100, delay='3ms', loss=0, cls=TCLink)

        # 5. Infrastructure Connections
        self.addLink(tmc, s1, bw=1000, delay='1ms', cls=TCLink)
        self.addLink(edge1, s2, bw=100, delay='2ms', cls=TCLink)
        self.addLink(edge2, s3, bw=100, delay='2ms', cls=TCLink)

        # 6. V2X Wireless Access Point Links (DSRC / 802.11p emulation: 20Mbps, 5ms delay, 1% loss)
        self.addLink(veh1, s2, bw=20, delay='5ms', loss=1, cls=TCLink)
        self.addLink(veh2, s2, bw=20, delay='5ms', loss=1, cls=TCLink)
        self.addLink(veh3, s3, bw=20, delay='5ms', loss=1, cls=TCLink)
        self.addLink(veh4, s3, bw=20, delay='5ms', loss=1, cls=TCLink)
        self.addLink(veh5, s4, bw=20, delay='5ms', loss=2, cls=TCLink)  # Attacker vehicle on s4
        self.addLink(veh6, s4, bw=20, delay='5ms', loss=1, cls=TCLink)


def create_its_topology(
    controller_ip: str = "127.0.0.1",
    controller_port: int = 6653,
    duration: int = 0,
    no_cli: bool = False,
):
    """Initializes and runs the Mininet ITS network emulation session.

    duration>0 + no_cli: headless lab mode (keeps topo up then stops).
    """
    if not MININET_AVAILABLE:
        print("[!] Mininet is not natively supported on Windows.")
        print("    Run this script on Linux / WSL2 / Mininet-WiFi container to instantiate the emulation environment.")
        print("    Dry-run simulation topology metadata:")
        print("    - Switches: s1 (Core), s2 (West RSU), s3 (East RSU), s4 (Highway RSU)")
        print("    - Hosts: tmc (10.0.0.1), edge1, edge2, veh1..veh6 (10.0.0.11..16)")
        print("    - Remote SDN Controller target:", f"{controller_ip}:{controller_port}")
        return None

    import time

    print("=" * 65)
    print("  INSTANTIATING MININET ITS EDGE NETWORK TOPOLOGY")
    print("=" * 65)

    topo = ITSEdgeTopology()
    # Default/OVS bridge mode works without a live Ryu process for ovs-ofctl lab agent
    if controller_port <= 0:
        net = Mininet(topo=topo, controller=None, link=TCLink, switch=OVSKernelSwitch)
    else:
        controller = RemoteController("c0", ip=controller_ip, port=controller_port)
        net = Mininet(topo=topo, controller=controller, link=TCLink, switch=OVSKernelSwitch)

    print("[*] Starting network & connecting switches...")
    net.start()
    print("[+] Network topology initialized successfully!")
    print("[*] Bridges: s1 s2 s3 s4 | hosts: tmc edge1 edge2 veh1..veh6")

    if no_cli or duration > 0:
        hold = duration if duration > 0 else 60
        print(f"[*] Headless lab mode — holding topology for {hold}s (Ctrl+C to stop)")
        try:
            time.sleep(hold)
        except KeyboardInterrupt:
            print("[*] Interrupted")
    else:
        print("[*] Launching Mininet Interactive CLI...")
        CLI(net)

    print("[*] Stopping network topology...")
    net.stop()
    return net


topos = {"its_topology": (lambda: ITSEdgeTopology())}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mininet ITS Network Topology Launcher")
    parser.add_argument("--controller_ip", type=str, default="127.0.0.1", help="Remote SDN Controller IP")
    parser.add_argument("--controller_port", type=int, default=0, help="OpenFlow port (0 = no remote controller)")
    parser.add_argument("--duration", type=int, default=0, help="Headless hold seconds (0 = CLI)")
    parser.add_argument("--no-cli", action="store_true", help="Do not open Mininet CLI")
    args = parser.parse_args()

    create_its_topology(
        controller_ip=args.controller_ip,
        controller_port=args.controller_port,
        duration=args.duration,
        no_cli=args.no_cli,
    )
