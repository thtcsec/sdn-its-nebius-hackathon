"""
controller.py - Modular SDN Resilience Controller & REST API Endpoint

Exposes a REST API service compatible with Ryu, ONOS, or standalone testbeds.
Receives real-time AI anomaly alerts and dynamically triggers OpenFlow 1.3 flow-rule updates.

Features:
- Closed-Loop Mitigation: Detect -> Contain -> Rollback
- REST API Endpoint: POST /api/v1/anomaly_alert
- Active Rule Tracking & History: GET /api/v1/active_rules, GET /api/v1/status
"""

import time
import argparse
from flask import Flask, request, jsonify, render_template
from typing import Dict, Any, Tuple
import os
import sys

# Ensure project root directory is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sdn_controller.flow_rules import FlowRuleManager, FlowRule


class ResilienceSDNController:
    """Core SDN Controller Management Component."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        
        # Initialize Flow Rule Manager with 5s cooldown check
        self.flow_mgr = FlowRuleManager(
            rollback_check_interval=2.0,
            of_push_callback=self._mock_openflow_switch_push
        )
        
        self.stats = {
            "total_alerts_received": 0,
            "mitigations_applied": 0,
            "false_positives_avoided": 0,
            "start_time": time.time()
        }
        
        self._register_routes()

    def _mock_openflow_switch_push(self, action: str, rule: FlowRule):
        """Simulates pushing OpenFlow OFPT_FLOW_MOD message over OpenFlow TCP channel / RESTCONF."""
        print(f"[OpenFlow Switch Channel] {action} Rule [{rule.rule_id}] -> DPID={rule.dpid}, Match={rule.src_ip}, Action={rule.action}")

    def _register_routes(self):
        @self.app.route("/", methods=["GET"])
        def index():
            return render_template("index.html")

        @self.app.route("/api/v1/status", methods=["GET"])
        def status():
            uptime_sec = time.time() - self.stats["start_time"]
            return jsonify({
                "status": "ONLINE",
                "service": "SDN ITS AI Resilience Controller",
                "uptime_seconds": round(uptime_sec, 1),
                "stats": self.stats,
                "active_mitigations_count": len(self.flow_mgr.active_rules)
            }), 200

        @self.app.route("/api/v1/active_rules", methods=["GET"])
        def get_active_rules():
            return jsonify({
                "count": len(self.flow_mgr.active_rules),
                "active_rules": self.flow_mgr.get_all_active_rules()
            }), 200

        @self.app.route("/api/v1/rollback_history", methods=["GET"])
        def get_rollback_history():
            return jsonify({
                "count": len(self.flow_mgr.rollback_history),
                "history": self.flow_mgr.rollback_history
            }), 200

        @self.app.route("/api/v1/anomaly_alert", methods=["POST"])
        def handle_anomaly_alert():
            """
            Endpoint receiving real-time AI anomaly alerts.
            
            Payload format:
            {
                "alert_id": "ALT-9823",
                "dpid": "0000000000000001",
                "src_ip": "10.0.0.15",
                "dst_ip": "10.0.0.1",
                "attack_type": "DDoS_PacketIn_Flood",
                "reconstruction_error": 1.482,
                "confidence": 0.985,
                "cooldown_seconds": 30
            }
            """
            data = request.get_json(force=True, silent=True)
            if not data or "attack_type" not in data or "dpid" not in data:
                return jsonify({"error": "Invalid payload format. Required: 'attack_type', 'dpid'"}), 400
                
            self.stats["total_alerts_received"] += 1
            
            alert_id = data.get("alert_id", f"ALT-{int(time.time())}")
            dpid = data["dpid"]
            src_ip = data.get("src_ip", "10.0.0.15")
            dst_ip = data.get("dst_ip", None)
            attack_type = data["attack_type"]
            cooldown = float(data.get("cooldown_seconds", 30.0))
            
            print(f"\n[ALERT RECEIVED] [{alert_id}] Type: {attack_type} | DPID: {dpid} | Src: {src_ip}")
            
            applied_rules = []
            mitigation_status = "NO_ACTION"
            
            # Closed-loop mitigation policy matrix
            if attack_type == "DDoS_PacketIn_Flood":
                # Containment: Drop offending src_ip & throttle packet_in overload
                rule1 = self.flow_mgr.create_drop_rule(dpid=dpid, src_ip=src_ip, dst_ip=dst_ip, priority=200, cooldown=cooldown)
                rule2 = self.flow_mgr.create_packet_in_throttle_rule(dpid=dpid, priority=250, cooldown=cooldown)
                applied_rules.extend([rule1.to_dict(), rule2.to_dict()])
                self.stats["mitigations_applied"] += 1
                mitigation_status = "CONTAINED_DROP_AND_THROTTLE"
                
            elif attack_type == "LOFT_LowRate_Attack":
                # Containment: Rate-limit low-rate flow requests
                rule = self.flow_mgr.create_rate_limit_rule(dpid=dpid, src_ip=src_ip, max_rate_kbps=500, priority=180, cooldown=cooldown)
                applied_rules.append(rule.to_dict())
                self.stats["mitigations_applied"] += 1
                mitigation_status = "CONTAINED_RATE_LIMITED"
                
            elif attack_type == "RSU_Link_Fault":
                print(f"[SDN Controller] RSU Link Fault detected on DPID {dpid}. Triggering path rerouting event.")
                mitigation_status = "REROUTED_RSU_FAULT"
                
            elif attack_type == "RushHour_Burst":
                # Legitimate mobility volume burst -> DO NOT BLOCK (Safety-aware false positive protection)
                print(f"[SDN Controller] Rush-hour burst identified on DPID {dpid}. Preserving legitimate V2X flow integrity.")
                self.stats["false_positives_avoided"] += 1
                mitigation_status = "IGNORED_BENIGN_RUSH_HOUR"
                
            return jsonify({
                "status": "SUCCESS",
                "alert_id": alert_id,
                "mitigation_status": mitigation_status,
                "applied_rules_count": len(applied_rules),
                "applied_rules": applied_rules,
                "cooldown_seconds": cooldown
            }), 200

    def run(self, debug: bool = False):
        print(f"[*] Starting SDN Resilience Controller REST API on {self.host}:{self.port}...")
        self.app.run(host=self.host, port=self.port, debug=debug, use_reloader=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start SDN Resilience Controller REST API")
    parser.add_argument("--port", type=int, default=8080, help="Controller REST API port")
    args = parser.parse_args()
    
    controller = ResilienceSDNController(port=args.port)
    controller.run()
