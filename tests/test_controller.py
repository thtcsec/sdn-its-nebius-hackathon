import unittest
import json
import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(PROJECT_ROOT, "src")
for p in (PROJECT_ROOT, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

from sdn_its.controller import ResilienceSDNController


class TestResilienceSDNController(unittest.TestCase):
    def setUp(self):
        self.controller = ResilienceSDNController()
        self.controller.app.config["TESTING"] = True
        self.client = self.controller.app.test_client()

    def tearDown(self):
        self.controller.flow_mgr.stop()

    def test_status_endpoint(self):
        response = self.client.get("/api/v1/status")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "ONLINE")
        self.assertIn("active_mitigations_count", data)

    def test_anomaly_alert_handling(self):
        payload_ddos = {
            "alert_id": "ALT-TEST-DDoS",
            "dpid": "0000000000000001",
            "src_ip": "10.0.0.15",
            "dst_ip": "10.0.0.1",
            "attack_type": "DDoS_PacketIn_Flood",
            "reconstruction_error": 1.5,
            "confidence": 0.99,
            "cooldown_seconds": 10.0,
        }
        resp = self.client.post("/api/v1/anomaly_alert", json=payload_ddos)
        self.assertEqual(resp.status_code, 200)
        data = resp.json
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["mitigation_status"], "CONTAINED_DROP_AND_THROTTLE")
        self.assertEqual(data["applied_rules_count"], 2)

        resp_rules = self.client.get("/api/v1/active_rules")
        rules_data = resp_rules.json
        self.assertEqual(rules_data["count"], 2)

        payload_rush = {
            "dpid": "0000000000000001",
            "attack_type": "RushHour_Burst",
            "cooldown_seconds": 0.0,
        }
        resp = self.client.post("/api/v1/anomaly_alert", json=payload_rush)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json["mitigation_status"], "IGNORED_BENIGN_RUSH_HOUR")


if __name__ == "__main__":
    unittest.main()
