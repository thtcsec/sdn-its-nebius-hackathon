"""Security helpers + lab console hardening."""

from __future__ import annotations

import os
import unittest

from sdn_its.controller import ResilienceSDNController
from sdn_its.utils.alerts import AlertNotifier
from sdn_its.utils.security import (
    is_loopback_bind,
    resolve_bind_host,
    validate_webhook_url,
)


class TestSecurityHardening(unittest.TestCase):
    def tearDown(self):
        for k in ("SDN_BIND_HOST", "SDN_HOST", "SDN_BIND_LAN", "SDN_API_TOKEN"):
            os.environ.pop(k, None)

    def test_default_bind_is_loopback(self):
        self.assertEqual(resolve_bind_host(None), "127.0.0.1")
        self.assertTrue(is_loopback_bind(resolve_bind_host(None)))

    def test_bind_lan_env(self):
        os.environ["SDN_BIND_LAN"] = "1"
        self.assertEqual(resolve_bind_host(None), "0.0.0.0")

    def test_controller_defaults_loopback(self):
        ctrl = ResilienceSDNController(create_flask=True)
        try:
            self.assertEqual(ctrl.host, "127.0.0.1")
            self.assertTrue(ctrl.stats.get("loopback_only"))
            client = ctrl.app.test_client()
            r = client.get("/api/v1/status")
            self.assertEqual(r.status_code, 200)
            self.assertIn("nosniff", r.headers.get("X-Content-Type-Options", ""))
        finally:
            ctrl.flow_mgr.stop()

    def test_api_token_blocks_mutating(self):
        os.environ["SDN_API_TOKEN"] = "lab-secret"
        ctrl = ResilienceSDNController(create_flask=True)
        try:
            client = ctrl.app.test_client()
            denied = client.post(
                "/api/v1/anomaly_alert",
                json={
                    "dpid": "0000000000000001",
                    "attack_type": "DDoS_PacketIn_Flood",
                    "src_ip": "10.0.0.15",
                },
            )
            self.assertEqual(denied.status_code, 401)
            ok = client.post(
                "/api/v1/anomaly_alert",
                json={
                    "dpid": "0000000000000001",
                    "attack_type": "DDoS_PacketIn_Flood",
                    "src_ip": "10.0.0.15",
                },
                headers={"X-API-Token": "lab-secret"},
            )
            self.assertEqual(ok.status_code, 200)
        finally:
            ctrl.flow_mgr.stop()

    def test_webhook_ssrf_blocks_metadata(self):
        ok, _ = validate_webhook_url("http://169.254.169.254/latest/meta-data")
        self.assertFalse(ok)
        ok2, _ = validate_webhook_url("http://127.0.0.1:9999/hooks")
        self.assertTrue(ok2)
        n = AlertNotifier()
        st = n.configure(webhook_url="http://169.254.169.254/", enabled=True)
        self.assertTrue(st.get("rejected_url"))
        self.assertFalse(st.get("enabled"))


if __name__ == "__main__":
    unittest.main()
