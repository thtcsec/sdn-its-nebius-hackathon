"""P0 security regressions for JunctionTrace / hackathon APIs.

Covers: unauthorized access, rate/concurrency abuse, budget exhaustion,
malformed input, server-enforced demo policy, audit protection, and
timeout fail-closed behavior. Never invokes a real Nebius endpoint.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from sdn_its.controller import ResilienceSDNController
from sdn_its.llm.hackathon_guard import (
    hosted_demo_enforced,
    reset_inference_guard_for_tests,
    resolve_demo_policy,
)
from sdn_its.utils.security import is_mutating_path, is_token_protected_path


class TestHackathonPathProtection(unittest.TestCase):
    def test_multistep_is_mutating(self):
        self.assertTrue(is_mutating_path("/api/v1/hackathon/multistep", "POST"))
        self.assertTrue(is_token_protected_path("/api/v1/hackathon/multistep", "POST"))

    def test_audit_get_protected_when_token_configured(self):
        self.assertTrue(is_token_protected_path("/api/v1/hackathon/audit", "GET"))
        self.assertFalse(is_mutating_path("/api/v1/hackathon/audit", "GET"))


class TestHostedDemoPolicy(unittest.TestCase):
    def tearDown(self):
        for k in ("SDN_API_TOKEN", "SDN_HOSTED_DEMO", "JT_HOSTED_DEMO"):
            os.environ.pop(k, None)

    def test_token_deployment_forces_demo_no_containment(self):
        os.environ["SDN_API_TOKEN"] = "judge-secret"
        self.assertTrue(hosted_demo_enforced())
        demo, allow, notes = resolve_demo_policy(False, True)
        self.assertTrue(demo)
        self.assertFalse(allow)
        self.assertIn("server_enforced_demo_policy", notes)

    def test_local_without_token_honors_client(self):
        os.environ.pop("SDN_API_TOKEN", None)
        os.environ.pop("SDN_HOSTED_DEMO", None)
        demo, allow, notes = resolve_demo_policy(True, False)
        self.assertTrue(demo)
        self.assertFalse(allow)
        self.assertEqual(notes, [])


class TestHackathonApiGuards(unittest.TestCase):
    def setUp(self):
        for k in (
            "SDN_API_TOKEN",
            "SDN_HOSTED_DEMO",
            "JT_HOSTED_DEMO",
            "NEBIUS_DAILY_BUDGET_USD",
            "JT_RATE_LIMIT_PER_MIN",
            "JT_MAX_CONCURRENT_REAL",
            "NEBIUS_API_KEY",
        ):
            os.environ.pop(k, None)
        reset_inference_guard_for_tests()

    def tearDown(self):
        for k in (
            "SDN_API_TOKEN",
            "SDN_HOSTED_DEMO",
            "JT_HOSTED_DEMO",
            "NEBIUS_DAILY_BUDGET_USD",
            "JT_RATE_LIMIT_PER_MIN",
            "JT_MAX_CONCURRENT_REAL",
            "NEBIUS_API_KEY",
        ):
            os.environ.pop(k, None)
        reset_inference_guard_for_tests()

    def _ctrl(self):
        return ResilienceSDNController(create_flask=True)

    def test_unauthorized_multistep_when_token_set(self):
        os.environ["SDN_API_TOKEN"] = "judge-secret"
        ctrl = self._ctrl()
        try:
            c = ctrl.app.test_client()
            r = c.post(
                "/api/v1/hackathon/multistep",
                json={"scenario_id": "scenario_rush_vs_attack", "mode": "offline", "demo_mode": True},
            )
            self.assertEqual(r.status_code, 401)
            self.assertEqual(r.get_json().get("error"), "unauthorized")
        finally:
            ctrl.flow_mgr.stop()

    def test_authorized_offline_multistep(self):
        os.environ["SDN_API_TOKEN"] = "judge-secret"
        ctrl = self._ctrl()
        try:
            c = ctrl.app.test_client()
            r = c.post(
                "/api/v1/hackathon/multistep",
                json={"scenario_id": "scenario_rush_vs_attack", "mode": "offline", "demo_mode": True},
                headers={"X-API-Token": "judge-secret"},
            )
            self.assertEqual(r.status_code, 200)
            body = r.get_json()
            self.assertEqual(body.get("evidence_class"), "deterministic_planner")
            self.assertTrue(body.get("demo_mode"))
            self.assertFalse(body.get("allow_containment_in_demo"))
            self.assertIn("server_enforced_demo_policy", body.get("server_policy_notes") or [])
            self.assertEqual(body.get("of_backend"), "mock")
        finally:
            ctrl.flow_mgr.stop()

    def test_unauthorized_audit_when_token_set(self):
        os.environ["SDN_API_TOKEN"] = "judge-secret"
        ctrl = self._ctrl()
        try:
            c = ctrl.app.test_client()
            denied = c.get("/api/v1/hackathon/audit")
            self.assertEqual(denied.status_code, 401)
            ok = c.get("/api/v1/hackathon/audit", headers={"Authorization": "Bearer judge-secret"})
            self.assertEqual(ok.status_code, 200)
            self.assertIn("audit", ok.get_json())
        finally:
            ctrl.flow_mgr.stop()

    def test_local_offline_works_without_token(self):
        ctrl = self._ctrl()
        try:
            c = ctrl.app.test_client()
            r = c.post(
                "/api/v1/hackathon/multistep",
                json={"scenario_id": "scenario_missing_camera", "mode": "offline", "demo_mode": True},
            )
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.get_json().get("evidence_class"), "deterministic_planner")
        finally:
            ctrl.flow_mgr.stop()

    def test_malformed_mode_rejected(self):
        ctrl = self._ctrl()
        try:
            c = ctrl.app.test_client()
            r = c.post(
                "/api/v1/hackathon/multistep",
                json={"scenario_id": "scenario_rush_vs_attack", "mode": "live-please"},
            )
            self.assertEqual(r.status_code, 400)
            self.assertIn("mode", (r.get_json().get("error") or "").lower())
        finally:
            ctrl.flow_mgr.stop()

    def test_malformed_telemetry_rejected(self):
        ctrl = self._ctrl()
        try:
            c = ctrl.app.test_client()
            r = c.post(
                "/api/v1/hackathon/multistep",
                json={"mode": "offline", "telemetry": "not-an-object", "camera": {}},
            )
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.get_json().get("error"), "malformed_input")
        finally:
            ctrl.flow_mgr.stop()

    def test_budget_exhausted_before_model(self):
        os.environ["NEBIUS_DAILY_BUDGET_USD"] = "0.01"
        guard = reset_inference_guard_for_tests()
        guard.record_spend(0.01)
        ctrl = self._ctrl()
        try:
            c = ctrl.app.test_client()
            with patch("sdn_its.llm.multi_step.run_multi_step_investigation") as mocked:
                r = c.post(
                    "/api/v1/hackathon/multistep",
                    json={"scenario_id": "scenario_loft_stable", "mode": "real", "demo_mode": True},
                )
                self.assertEqual(r.status_code, 429)
                body = r.get_json()
                self.assertEqual(body.get("error"), "budget_exhausted")
                self.assertEqual(body.get("evidence_class"), "blocked_guard")
                mocked.assert_not_called()
        finally:
            ctrl.flow_mgr.stop()

    def test_rate_limit_abuse_before_model(self):
        os.environ["JT_RATE_LIMIT_PER_MIN"] = "2"
        reset_inference_guard_for_tests()
        ctrl = self._ctrl()
        try:
            c = ctrl.app.test_client()

            def _fake_ms(*_a, **_k):
                m = MagicMock()
                m.ok = True
                m.evidence_class = "blocked_no_credentials"
                m.estimated_cost_usd = 0.0
                m.recommendation = None
                m.tool_calls = []
                m.gated_notes = []
                m.pre_gate_source = None
                m.conclusion_kind = "blocked"
                m.trace = []
                m.to_dict.return_value = {
                    "ok": False,
                    "evidence_class": "blocked_no_credentials",
                    "error": "no credentials",
                }
                return m

            with patch("sdn_its.llm.multi_step.run_multi_step_investigation", side_effect=_fake_ms):
                for _ in range(2):
                    r = c.post(
                        "/api/v1/hackathon/multistep",
                        json={"scenario_id": "scenario_loft_stable", "mode": "real", "demo_mode": True},
                    )
                    self.assertNotEqual(r.status_code, 429, r.get_json())
                r3 = c.post(
                    "/api/v1/hackathon/multistep",
                    json={"scenario_id": "scenario_loft_stable", "mode": "real", "demo_mode": True},
                )
                self.assertEqual(r3.status_code, 429)
                self.assertEqual(r3.get_json().get("error"), "rate_limited")
        finally:
            ctrl.flow_mgr.stop()

    def test_concurrency_limit_before_model(self):
        os.environ["JT_MAX_CONCURRENT_REAL"] = "1"
        guard = reset_inference_guard_for_tests()
        d = guard.check_real_allowed("hold")
        self.assertTrue(d.ok)
        ctrl = self._ctrl()
        try:
            c = ctrl.app.test_client()
            with patch("sdn_its.llm.multi_step.run_multi_step_investigation") as mocked:
                r = c.post(
                    "/api/v1/hackathon/multistep",
                    json={"scenario_id": "scenario_loft_stable", "mode": "real", "demo_mode": True},
                )
                self.assertEqual(r.status_code, 429)
                self.assertEqual(r.get_json().get("error"), "concurrency_limit")
                mocked.assert_not_called()
        finally:
            guard.release_slot()
            ctrl.flow_mgr.stop()

    def test_client_cannot_disable_demo_on_hosted(self):
        os.environ["SDN_API_TOKEN"] = "judge-secret"
        ctrl = self._ctrl()
        try:
            c = ctrl.app.test_client()
            r = c.post(
                "/api/v1/hackathon/multistep",
                json={
                    "scenario_id": "scenario_rush_vs_attack",
                    "mode": "offline",
                    "demo_mode": False,
                    "allow_containment_in_demo": True,
                },
                headers={"X-API-Token": "judge-secret"},
            )
            self.assertEqual(r.status_code, 200)
            body = r.get_json()
            self.assertTrue(body.get("demo_mode"))
            self.assertFalse(body.get("allow_containment_in_demo"))
        finally:
            ctrl.flow_mgr.stop()

    def test_timeout_fail_closed_observe(self):
        """Timeout must return fail-closed observe — never drop/block."""
        ctrl = self._ctrl()
        try:
            c = ctrl.app.test_client()
            with patch(
                "sdn_its.llm.multi_step.run_multi_step_investigation",
                side_effect=TimeoutError("nebius request timed out"),
            ):
                r = c.post(
                    "/api/v1/hackathon/multistep",
                    json={"scenario_id": "scenario_loft_stable", "mode": "real", "demo_mode": True},
                )
            self.assertEqual(r.status_code, 502)
            body = r.get_json()
            self.assertEqual(body.get("error"), "timeout")
            self.assertEqual((body.get("recommendation") or {}).get("recommended_action"), "observe")
            self.assertEqual(body.get("of_backend"), "mock")
        finally:
            ctrl.flow_mgr.stop()


class TestGuardUnit(unittest.TestCase):
    def tearDown(self):
        for k in ("NEBIUS_DAILY_BUDGET_USD", "JT_RATE_LIMIT_PER_MIN", "JT_MAX_CONCURRENT_REAL"):
            os.environ.pop(k, None)
        reset_inference_guard_for_tests()

    def test_budget_and_release(self):
        os.environ["NEBIUS_DAILY_BUDGET_USD"] = "0.05"
        g = reset_inference_guard_for_tests()
        d = g.check_real_allowed("a")
        self.assertTrue(d.ok)
        g.release_slot()
        g.record_spend(0.05)
        d2 = g.check_real_allowed("a")
        self.assertFalse(d2.ok)
        self.assertEqual(d2.error, "budget_exhausted")


if __name__ == "__main__":
    unittest.main()
