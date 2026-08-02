"""API smoke tests for settings POST, infer, replay, telemetry."""

from __future__ import annotations

import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(PROJECT_ROOT, "src")
for p in (PROJECT_ROOT, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

from sdn_its.controller import ResilienceSDNController


class TestUpgradeAPIs(unittest.TestCase):
    def setUp(self):
        self.controller = ResilienceSDNController()
        self.controller.app.config["TESTING"] = True
        self.client = self.controller.app.test_client()

    def tearDown(self):
        self.controller.flow_mgr.stop()

    def test_settings_get_post(self):
        r = self.client.get("/api/v1/settings")
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertIn("console_defaults", body)
        self.assertIn("features", body)

        r2 = self.client.post(
            "/api/v1/settings",
            json={"tau": 42.5, "theme": "dark", "role_mode": "demo", "k_sigma": 2.5},
        )
        self.assertEqual(r2.status_code, 200)
        runtime = r2.get_json()["runtime"]
        self.assertEqual(runtime["tau"], 42.5)
        self.assertEqual(runtime["theme"], "dark")

    def test_infer_and_telemetry(self):
        r = self.client.post("/api/v1/infer", json={"scenario": "normal", "adapt_tau": True})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("reconstruction_error", data)
        self.assertIn("threshold_tau", data)
        self.assertIn("attribution", data)

        r2 = self.client.get("/api/v1/telemetry?scenario=normal")
        self.assertEqual(r2.status_code, 200)
        self.assertIn("reconstruction_error", r2.get_json())

    def test_replay_scripts(self):
        r = self.client.get("/api/v1/replay")
        self.assertEqual(r.status_code, 200)
        self.assertIn("full_story", r.get_json()["scripts"])

        r2 = self.client.post("/api/v1/replay", json={"script": "ddos_cycle"})
        self.assertEqual(r2.status_code, 200)
        self.assertGreater(len(r2.get_json()["steps"]), 0)

        step = r2.get_json()["steps"][1]
        r3 = self.client.post("/api/v1/replay/step", json=step)
        self.assertEqual(r3.status_code, 200)
        self.assertIn("score", r3.get_json())

    def test_export_report(self):
        prev = self.client.get("/api/v1/export/report")
        self.assertEqual(prev.status_code, 200)
        self.assertIn("markdown", prev.get_json())
        self.assertIn("SDN-ITS Console Snapshot", prev.get_json()["markdown"])

        r = self.client.post("/api/v1/export/report", json={"name": "unit_test_report"})
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        path = body["path"]
        self.assertTrue(os.path.exists(os.path.join(PROJECT_ROOT, path)))
        self.assertIn("markdown", body)
        self.assertTrue(body["markdown"].startswith("# SDN-ITS Console Snapshot"))
        dl = self.client.get(f"/api/v1/export/report/file?path={path}")
        self.assertEqual(dl.status_code, 200)

    def test_topology_and_latency(self):
        self.assertEqual(self.client.get("/api/v1/topology").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/latency_cdf").status_code, 200)


if __name__ == "__main__":
    unittest.main()
