"""Unit tests for camera fusion + policy remapping."""

from __future__ import annotations

import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(PROJECT_ROOT, "src")
for p in (PROJECT_ROOT, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

from sdn_its.camera.fusion import FusionEngine
from sdn_its.camera.store import get_camera_store
from sdn_its.controller import ResilienceSDNController


class TestCameraFusion(unittest.TestCase):
    def test_rush_with_ddos_label_preserves(self):
        eng = FusionEngine()
        d = eng.fuse(
            network_prediction="DDoS_PacketIn_Flood",
            physical={
                "physical_label": "rush_hour",
                "is_vehicle_count": True,
                "vehicle_count": 40,
                "queue_length_m": 50,
                "activity_band": "high",
                "pedestrian_present": False,
                "incident": False,
                "stale": False,
                "analytics_valid": True,
            },
            source_dominance=0.3,
            distributed_sources=True,
            packet_in_delta_pct=400,
        )
        self.assertEqual(d.recommended_action, "preserve_rush_hour")
        self.assertTrue(d.false_positive_corrected)

    def test_stable_camera_contains_flood(self):
        eng = FusionEngine()
        d = eng.fuse(
            network_prediction="DDoS_PacketIn_Flood",
            physical={
                "physical_label": "stable",
                "is_vehicle_count": True,
                "vehicle_count": 5,
                "queue_length_m": 4,
                "activity_band": "low",
                "pedestrian_present": False,
                "incident": False,
                "stale": False,
                "analytics_valid": True,
            },
            source_dominance=0.85,
            distributed_sources=False,
            packet_in_delta_pct=400,
        )
        self.assertEqual(d.recommended_action, "temporary_drop")

    def test_proxy_band_does_not_claim_vehicle_count(self):
        eng = FusionEngine()
        d = eng.fuse(
            network_prediction="DDoS_PacketIn_Flood",
            physical={
                "physical_label": "rush_hour",
                "is_vehicle_count": False,
                "vehicle_count": None,
                "activity_band": "high",
                "visual_activity": {
                    "metric": "visual_activity_proxy",
                    "value": 32.0,
                    "source": "edge_energy",
                    "is_vehicle_count": False,
                    "activity_band": "high",
                },
                "stale": False,
                "analytics_valid": True,
            },
            source_dominance=0.3,
            distributed_sources=True,
            packet_in_delta_pct=400,
        )
        self.assertEqual(d.recommended_action, "preserve_rush_hour")
        self.assertIn("VISUAL_ACTIVITY_PROXY_NOT_DETECTOR", d.reason_codes)
        self.assertIn("HIGH_VISUAL_ACTIVITY_PROXY", d.reason_codes)

    def test_controller_alert_includes_fusion(self):
        store = get_camera_store()
        store.set_scenario("attack_physical_stable")
        ctrl = ResilienceSDNController(create_flask=True)
        ctrl.app.config["TESTING"] = True
        client = ctrl.app.test_client()
        try:
            resp = client.post(
                "/api/v1/anomaly_alert",
                json={
                    "dpid": "0000000000000001",
                    "src_ip": "10.0.0.15",
                    "attack_type": "DDoS_PacketIn_Flood",
                    "prediction": "DDoS_PacketIn_Flood",
                    "camera_scenario": "attack_physical_stable",
                    "source_dominance": 0.85,
                    "packet_in_delta_pct": 400,
                    "cooldown_seconds": 10,
                },
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json
            self.assertIn("fusion", data)
            self.assertEqual(data["mitigation_status"], "CONTAINED_DROP_AND_THROTTLE")
            cam = client.get("/api/v1/camera").json
            self.assertIn("cameras", cam)
            self.assertGreaterEqual(len(cam["cameras"]), 1)
            agg = cam.get("aggregate") or {}
            self.assertTrue(agg.get("is_vehicle_count") or agg.get("vehicle_count_is_real"))
        finally:
            ctrl.flow_mgr.stop()


if __name__ == "__main__":
    unittest.main()
