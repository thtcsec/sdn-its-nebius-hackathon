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

import sys
import os
import argparse
from typing import Dict, Any, List

# Mininet / Mininet-WiFi imports (wrapped with graceful fallback for non-Linux platforms)
try:
    from mininet.topo import Topo
    from mininet.net import Mininet
    from mininet.node import RemoteController, OVSKernelSwitch
    from mininet.link import TCLink
    from mininet.cli import CLI
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


def create_its_topology(controller_ip: str = '127.0.0.1', controller_port: int = 6653):
    """Initializes and runs the Mininet ITS network emulation session."""
    if not MININET_AVAILABLE:
        print("[!] Mininet is not natively supported on Windows.")
        print("    Run this script on Linux / WSL2 / Mininet-WiFi container to instantiate the emulation environment.")
        print("    Dry-run simulation topology metadata:")
        print("    - Switches: s1 (Core), s2 (West RSU), s3 (East RSU), s4 (Highway RSU)")
        print("    - Hosts: tmc (10.0.0.1), edge1, edge2, veh1..veh6 (10.0.0.11..16)")
        print("    - Remote SDN Controller target:", f"{controller_ip}:{controller_port}")
        return

    print("=" * 65)
    print("  INSTANTIATING MININET ITS EDGE NETWORK TOPOLOGY")
    print("=" * 65)
    
    topo = ITSEdgeTopology()
    controller = RemoteController('c0', ip=controller_ip, port=controller_port)
    net = Mininet(topo=topo, controller=controller, link=TCLink, switch=OVSKernelSwitch)
    
    print("[*] Starting network & connecting switches to SDN Controller...")
    net.start()
    
    print("[+] Network topology initialized successfully!")
    print("[*] Launching Mininet Interactive Command Line Interface (CLI)...")
    CLI(net)
    
    print("[*] Stopping network topology...")
    net.stop()


topos = {'its_topology': (lambda: ITSEdgeTopology())}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Mininet ITS Network Topology Launcher")
    parser.add_argument("--controller_ip", type=str, default="127.0.0.1", help="Remote SDN Controller IP")
    parser.add_argument("--controller_port", type=int, default=6653, help="OpenFlow port (6653 default)")
    args = parser.parse_args()
    
    create_its_topology(controller_ip=args.controller_ip, controller_port=args.controller_port)
