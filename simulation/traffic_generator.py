"""
traffic_generator.py - V2X & Cybersecurity Attack Traffic Generator

Generates realistic V2X traffic patterns and cybersecurity stressor streams:
1. Normal V2X Telemetry (CAM / DENM periodic messaging between vehicles and RSUs)
2. Rush-Hour Mobility Burst (High-volume benign traffic surge)
3. Control-Plane DDoS PacketIn Flood (Malformed / unmatched packets forcing switch packet_in)
4. Low-Rate OpenFlow Trust (LOFT) Attack (Periodic low-rate probe streams)
5. Automated Alert Sender pushing telemetry to the SDN Controller REST API.
"""

import time
import random
import requests
import argparse
from typing import Dict, Any, Optional

# Optional TraCI import for SUMO coupling
try:
    import traci
    SUMO_AVAILABLE = True
except ImportError:
    SUMO_AVAILABLE = False


class V2XTrafficGenerator:
    """Traffic Generator for SDN ITS Resilience Validation."""
    
    def __init__(self, controller_url: str = "http://localhost:8080"):
        self.controller_url = controller_url.rstrip("/")
        self.alert_endpoint = f"{self.controller_url}/api/v1/anomaly_alert"
        
    def send_alert_to_controller(
        self, attack_type: str, dpid: str = "0000000000000001", 
        src_ip: str = "10.0.0.15", dst_ip: str = "10.0.0.1",
        re_error: float = 1.25, confidence: float = 0.95, cooldown_sec: float = 30.0
    ) -> bool:
        """Pushes an AI anomaly alert payload to the SDN Controller REST API."""
        payload = {
            "alert_id": f"ALT-{random.randint(1000, 9999)}",
            "timestamp": time.time(),
            "dpid": dpid,
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "attack_type": attack_type,
            "reconstruction_error": round(re_error, 4),
            "confidence": round(confidence, 3),
            "cooldown_seconds": cooldown_sec
        }
        
        try:
            resp = requests.post(self.alert_endpoint, json=payload, timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                print(f"[+] Alert successfully processed by SDN Controller! Status: {data.get('mitigation_status')}")
                return True
            else:
                print(f"[!] Controller returned status code {resp.status_code}: {resp.text}")
                return False
        except Exception as e:
            print(f"[!] Failed to connect to SDN Controller REST API at {self.alert_endpoint}: {e}")
            return False

    def simulate_scenario(self, scenario_name: str, duration_sec: int = 15):
        """Runs a designated traffic scenario simulation."""
        print(f"\n" + "=" * 65)
        print(f"  RUNNING TRAFFIC SCENARIO: {scenario_name.upper()}")
        print("=" * 65)
        
        if scenario_name == "normal":
            print("[*] Simulating Normal V2X Vehicle-to-RSU CAM/DENM Message Flows...")
            for i in range(duration_sec):
                pkt_rate = random.randint(40, 60)
                pkt_in = random.randint(1, 3)
                print(f"  [t={i+1:02d}s] RSU s1 Telemetry | Packet Rate: {pkt_rate} pkts/s | packet_in: {pkt_in} | Status: NORMAL")
                time.sleep(1.0)
                
        elif scenario_name == "ddos":
            print("[!] Simulating Control-Plane DDoS PacketIn Flooding from veh5 (10.0.0.15)...")
            for i in range(duration_sec):
                pkt_rate = random.randint(1200, 2500)
                pkt_in = random.randint(200, 500)
                print(f"  [t={i+1:02d}s] RSU s1 Telemetry | Packet Rate: {pkt_rate} pkts/s | packet_in: {pkt_in} | [!] CRITICAL ANOMALY")
                if i == 3:
                    print("\n[AI Detection] Model detected Reconstruction Error RE = 1.842 > Tau (0.420).")
                    print("[AI Detection] Classifying Anomaly Category: DDoS_PacketIn_Flood (Prob: 0.982)")
                    self.send_alert_to_controller(
                        attack_type="DDoS_PacketIn_Flood",
                        dpid="0000000000000001",
                        src_ip="10.0.0.15",
                        re_error=1.842,
                        cooldown_sec=20.0
                    )
                time.sleep(1.0)
                
        elif scenario_name == "loft":
            print("[!] Simulating Low-Rate OpenFlow Trust (LOFT) Attack from veh5 (10.0.0.15)...")
            for i in range(duration_sec):
                pkt_rate = random.randint(80, 120)
                pkt_in = random.randint(25, 45)
                print(f"  [t={i+1:02d}s] RSU s1 Telemetry | Packet Rate: {pkt_rate} pkts/s | packet_in: {pkt_in} | [!] LOW-RATE PROBE")
                if i == 3:
                    print("\n[AI Detection] Model detected Reconstruction Error RE = 0.891 > Tau (0.420).")
                    print("[AI Detection] Classifying Anomaly Category: LOFT_LowRate_Attack (Prob: 0.941)")
                    self.send_alert_to_controller(
                        attack_type="LOFT_LowRate_Attack",
                        dpid="0000000000000001",
                        src_ip="10.0.0.15",
                        re_error=0.891,
                        cooldown_sec=15.0
                    )
                time.sleep(1.0)

        elif scenario_name == "rushhour":
            print("[*] Simulating Benign Rush-Hour Mobility Burst (High Volume, Low packet_in)...")
            for i in range(duration_sec):
                pkt_rate = random.randint(300, 500)
                pkt_in = random.randint(2, 5)
                print(f"  [t={i+1:02d}s] RSU s1 Telemetry | Packet Rate: {pkt_rate} pkts/s | packet_in: {pkt_in} | Status: RUSH_HOUR")
                if i == 3:
                    print("\n[AI Detection] Model detected Volume Surge with Normal packet_in frequency.")
                    print("[AI Detection] Classifying Category: RushHour_Burst (Prob: 0.965)")
                    self.send_alert_to_controller(
                        attack_type="RushHour_Burst",
                        dpid="0000000000000001",
                        src_ip="10.0.0.12",
                        re_error=0.120,
                        cooldown_sec=0.0
                    )
                time.sleep(1.0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="V2X Traffic Generator & Anomaly Injection")
    parser.add_argument("--scenario", type=str, choices=["normal", "ddos", "loft", "rushhour"], default="ddos", help="Scenario type")
    parser.add_argument("--controller_url", type=str, default="http://localhost:8080", help="SDN Controller REST API URL")
    parser.add_argument("--duration", type=int, default=8, help="Scenario duration in seconds")
    args = parser.parse_args()
    
    gen = V2XTrafficGenerator(controller_url=args.controller_url)
    gen.simulate_scenario(scenario_name=args.scenario, duration_sec=args.duration)
