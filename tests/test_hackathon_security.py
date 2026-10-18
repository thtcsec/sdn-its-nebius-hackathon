"""Hosted security gate regressions for JunctionTrace.

Covers: startup fail-closed, shared quota on all model routes, persistent
budget across restarts, spoofed XFF, concurrency, legacy route policy,
containment blocking. Distinguishes credential-free vs mocked-provider paths.
Never requires a live Nebius call for these assertions.
"""

from __future__ import annotations

import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from sdn_its.controller import ResilienceSDNController
from sdn_its.llm.hackathon_guard import (
    HostedConfigError,
    client_rate_identity,
    hosted_demo_enforced,
    legacy_model_routes_disabled,
    reset_inference_guard_for_tests,
    resolve_demo_policy,
    resolve_request_safety_flags,
    token_is_secure,
    validate_hosted_startup,
)
from sdn_its.utils.security import is_mutating_path, is_token_protected_path


def _clear_env(*keys: str) -> None:
    for k in keys:
        os.environ.pop(k, None)


_ENV_KEYS = (
    "SDN_API_TOKEN",
    "SDN_HOSTED_DEMO",
    "JT_HOSTED_DEMO",
    "NEBIUS_DAILY_BUDGET_USD",
    "JT_RATE_LIMIT_PER_MIN",
    "JT_MAX_CONCURRENT_REAL",
    "JT_RESERVE_USD_PER_REAL",
    "JT_QUOTA_DB_PATH",
    "JT_TRUSTED_PROXY",
    "NEBIUS_API_KEY",
    "SDN_OF_BACKEND",
)


class TestPathProtection(unittest.TestCase):
    def test_all_model_routes_are_token_protected(self):
        for path in (
            "/api/v1/hackathon/multistep",
            "/api/v1/hackathon/run",
            "/api/v1/hackathon/investigate",
        ):
            self.assertTrue(is_mutating_path(path, "POST"), path)
            self.assertTrue(is_token_protected_path(path, "POST"), path)
        self.assertTrue(is_token_protected_path("/api/v1/hackathon/audit", "GET"))


class TestHostedStartup(unittest.TestCase):
    def tearDown(self):
        _clear_env(*_ENV_KEYS)

    def test_missing_hosted_token_refuses_start(self):
        os.environ["SDN_HOSTED_DEMO"] = "1"
        _clear_env("SDN_API_TOKEN")
        with self.assertRaises(HostedConfigError):
            validate_hosted_startup(bind_host="0.0.0.0", of_backend="mock")

    def test_weak_hosted_token_refuses_start(self):
        os.environ["SDN_HOSTED_DEMO"] = "1"
        os.environ["SDN_API_TOKEN"] = "changeme"
        self.assertFalse(token_is_secure("changeme"))
        with self.assertRaises(HostedConfigError):
            validate_hosted_startup(bind_host="0.0.0.0", of_backend="mock")

    def test_non_mock_of_refuses_start(self):
        os.environ["SDN_HOSTED_DEMO"] = "1"
        os.environ["SDN_API_TOKEN"] = "judge-token-secure-01"
        with self.assertRaises(HostedConfigError):
            validate_hosted_startup(bind_host="0.0.0.0", of_backend="ryu")

    def test_create_app_fails_closed_hosted(self):
        os.environ["SDN_HOSTED_DEMO"] = "1"
        _clear_env("SDN_API_TOKEN")
        from api.app import create_app

        with self.assertRaises(HostedConfigError):
            create_app()

    def test_local_loopback_starts_without_token(self):
        _clear_env("SDN_HOSTED_DEMO", "SDN_API_TOKEN")
        from api.app import create_app

        app = create_app()
        self.assertIsNotNone(app)
        # research route still registered
        c = app.test_client()
        r = c.get("/research")
        self.assertEqual(r.status_code, 200)


class TestClientIdentity(unittest.TestCase):
    def tearDown(self):
        _clear_env("JT_TRUSTED_PROXY")

    def test_ignores_spoofed_xff_by_default(self):
        a = client_rate_identity(remote_addr="10.0.0.5", x_forwarded_for="1.2.3.4")
        b = client_rate_identity(remote_addr="10.0.0.5", x_forwarded_for="9.9.9.9")
        self.assertEqual(a, b)
        self.assertEqual(a, "ip:10.0.0.5")

    def test_trusted_proxy_uses_xff(self):
        os.environ["JT_TRUSTED_PROXY"] = "1"
        a = client_rate_identity(remote_addr="10.0.0.5", x_forwarded_for="1.2.3.4, 10.0.0.5")
        self.assertEqual(a, "xff:1.2.3.4")


class TestPersistentQuota(unittest.TestCase):
    def setUp(self):
        _clear_env(*_ENV_KEYS)
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmpdir.name) / "quota.sqlite"
        os.environ["NEBIUS_DAILY_BUDGET_USD"] = "0.10"
        os.environ["JT_RESERVE_USD_PER_REAL"] = "0.05"
        os.environ["JT_MAX_CONCURRENT_REAL"] = "2"
        os.environ["JT_RATE_LIMIT_PER_MIN"] = "20"
        os.environ["JT_QUOTA_DB_PATH"] = str(self.db)

    def tearDown(self):
        _clear_env(*_ENV_KEYS)
        reset_inference_guard_for_tests()  # close previous DB handle first
        self._tmpdir.cleanup()

    def test_budget_blocks_before_model_and_survives_restart(self):
        g1 = reset_inference_guard_for_tests(self.db)
        d1 = g1.admit_real("ip:1.1.1.1")
        self.assertTrue(d1.ok)
        g1.settle(d1.reservation_id, estimated_usd=0.05)
        d2 = g1.admit_real("ip:1.1.1.1")
        self.assertTrue(d2.ok)
        g1.settle(d2.reservation_id, estimated_usd=0.05)
        d3 = g1.admit_real("ip:1.1.1.1")
        self.assertFalse(d3.ok)
        self.assertEqual(d3.error, "budget_exhausted")

        # New process / new guard instance, same DB — still exhausted
        g2 = reset_inference_guard_for_tests(self.db)
        d4 = g2.admit_real("ip:2.2.2.2")
        self.assertFalse(d4.ok)
        self.assertEqual(d4.error, "budget_exhausted")
        snap = g2.snapshot()
        self.assertGreaterEqual(snap["estimated_spent_usd"], 0.10 - 1e-9)

    def test_concurrent_admit_respects_inflight(self):
        os.environ["JT_MAX_CONCURRENT_REAL"] = "1"
        os.environ["NEBIUS_DAILY_BUDGET_USD"] = "10"
        g = reset_inference_guard_for_tests(self.db)
        results: list[bool] = []
        barrier = threading.Barrier(4)

        def worker():
            barrier.wait()
            d = g.admit_real("ip:concurrent")
            results.append(d.ok)
            if d.ok:
                # hold briefly
                import time

                time.sleep(0.15)
                g.settle(d.reservation_id, estimated_usd=0.001)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sum(1 for ok in results if ok), 1)
        self.assertEqual(sum(1 for ok in results if not ok), 3)

    def test_spoofed_xff_does_not_bypass_rate_limit(self):
        os.environ["JT_RATE_LIMIT_PER_MIN"] = "2"
        os.environ["NEBIUS_DAILY_BUDGET_USD"] = "10"
        g = reset_inference_guard_for_tests(self.db)
        key = client_rate_identity(remote_addr="127.0.0.1", x_forwarded_for="8.8.8.8")
        for _ in range(2):
            d = g.admit_real(key)
            self.assertTrue(d.ok)
            g.settle(d.reservation_id, estimated_usd=0.0)
        # Different spoofed XFF, same remote — still rate limited
        key2 = client_rate_identity(remote_addr="127.0.0.1", x_forwarded_for="1.1.1.1")
        self.assertEqual(key, key2)
        d3 = g.admit_real(key2)
        self.assertFalse(d3.ok)
        self.assertEqual(d3.error, "rate_limited")


class TestApiSharedGuard(unittest.TestCase):
    def setUp(self):
        _clear_env(*_ENV_KEYS)
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmpdir.name) / "api_quota.sqlite"
        os.environ["JT_QUOTA_DB_PATH"] = str(self.db)
        os.environ["NEBIUS_DAILY_BUDGET_USD"] = "0.05"
        os.environ["JT_RESERVE_USD_PER_REAL"] = "0.05"
        os.environ["JT_RATE_LIMIT_PER_MIN"] = "20"
        reset_inference_guard_for_tests(self.db)

    def tearDown(self):
        _clear_env(*_ENV_KEYS)
        reset_inference_guard_for_tests()
        self._tmpdir.cleanup()

    def _ctrl(self):
        return ResilienceSDNController(create_flask=True)

    def test_unauthorized_all_model_routes(self):
        os.environ["SDN_API_TOKEN"] = "judge-token-secure-01"
        ctrl = self._ctrl()
        try:
            c = ctrl.app.test_client()
            for path in (
                "/api/v1/hackathon/multistep",
                "/api/v1/hackathon/run",
                "/api/v1/hackathon/investigate",
            ):
                r = c.post(path, json={"mode": "offline", "scenario_id": "scenario_rush_vs_attack"})
                self.assertEqual(r.status_code, 401, path)
        finally:
            ctrl.flow_mgr.stop()

    def test_legacy_disabled_under_hosted_demo(self):
        os.environ["SDN_HOSTED_DEMO"] = "1"
        os.environ["SDN_API_TOKEN"] = "judge-token-secure-01"
        os.environ["SDN_OF_BACKEND"] = "mock"
        self.assertTrue(legacy_model_routes_disabled())
        from api.app import create_app

        app = create_app()
        c = app.test_client()
        headers = {"X-API-Token": "judge-token-secure-01"}
        for path in ("/api/v1/hackathon/run", "/api/v1/hackathon/investigate"):
            r = c.post(path, json={"mode": "offline", "demo_mode": False}, headers=headers)
            self.assertEqual(r.status_code, 410, path)
            self.assertEqual(r.get_json().get("error"), "legacy_route_disabled")

    def test_legacy_cannot_disable_safety_when_token_set(self):
        os.environ["SDN_API_TOKEN"] = "judge-token-secure-01"
        # Not HOSTED_DEMO — legacy stays open for research, but policy forced
        ctrl = self._ctrl()
        try:
            c = ctrl.app.test_client()
            r = c.post(
                "/api/v1/hackathon/run",
                json={
                    "scenario_id": "scenario_rush_vs_attack",
                    "mode": "offline",
                    "demo_mode": False,
                    "allow_containment_in_demo": True,
                },
                headers={"X-API-Token": "judge-token-secure-01"},
            )
            self.assertEqual(r.status_code, 200)
            body = r.get_json()
            self.assertTrue(body.get("demo_mode"))
            self.assertFalse(body.get("allow_containment_in_demo"))
            self.assertIn("server_enforced_demo_policy", body.get("server_policy_notes") or [])
        finally:
            ctrl.flow_mgr.stop()

    def test_budget_shared_across_routes_before_model(self):
        # Exhaust via multistep admit, then run/investigate/multistep all blocked
        os.environ["SDN_API_TOKEN"] = "judge-token-secure-01"
        g = reset_inference_guard_for_tests(self.db)
        d = g.admit_real("ip:127.0.0.1")
        self.assertTrue(d.ok)
        g.settle(d.reservation_id, estimated_usd=0.05)

        ctrl = self._ctrl()
        try:
            c = ctrl.app.test_client()
            headers = {"X-API-Token": "judge-token-secure-01"}
            with patch("sdn_its.llm.multi_step.run_multi_step_investigation") as m_ms, patch(
                "sdn_its.llm.agent.investigate_case"
            ) as m_run, patch("sdn_its.llm.investigation.investigate_incident") as m_inv:
                for path, body in (
                    (
                        "/api/v1/hackathon/multistep",
                        {"scenario_id": "scenario_loft_stable", "mode": "real"},
                    ),
                    (
                        "/api/v1/hackathon/run",
                        {"scenario_id": "scenario_loft_stable", "mode": "real"},
                    ),
                    (
                        "/api/v1/hackathon/investigate",
                        {"network_prediction": "DDoS_PacketIn_Flood", "telemetry": {}, "camera": {}},
                    ),
                ):
                    r = c.post(path, json=body, headers=headers)
                    self.assertEqual(r.status_code, 429, path)
                    self.assertEqual(r.get_json().get("error"), "budget_exhausted", path)
                m_ms.assert_not_called()
                m_run.assert_not_called()
                m_inv.assert_not_called()
        finally:
            ctrl.flow_mgr.stop()

    def test_xff_spoof_via_http_does_not_bypass_rate(self):
        os.environ["JT_RATE_LIMIT_PER_MIN"] = "2"
        os.environ["NEBIUS_DAILY_BUDGET_USD"] = "10"
        os.environ["JT_RESERVE_USD_PER_REAL"] = "0.01"
        reset_inference_guard_for_tests(self.db)
        ctrl = self._ctrl()
        try:
            c = ctrl.app.test_client()

            def _fake(*_a, **_k):
                m = MagicMock()
                m.ok = False
                m.evidence_class = "blocked_no_credentials"
                m.estimated_cost_usd = 0.0
                m.recommendation = None
                m.tool_calls = []
                m.gated_notes = []
                m.pre_gate_source = None
                m.conclusion_kind = "blocked"
                m.trace = []
                m.to_dict.return_value = {"ok": False, "evidence_class": "blocked_no_credentials"}
                return m

            with patch("sdn_its.llm.multi_step.run_multi_step_investigation", side_effect=_fake):
                for i, xff in enumerate(("1.1.1.1", "2.2.2.2")):
                    r = c.post(
                        "/api/v1/hackathon/multistep",
                        json={"scenario_id": "scenario_loft_stable", "mode": "real"},
                        headers={"X-Forwarded-For": xff},
                    )
                    self.assertNotEqual(r.status_code, 429, f"call {i}")
                r3 = c.post(
                    "/api/v1/hackathon/multistep",
                    json={"scenario_id": "scenario_loft_stable", "mode": "real"},
                    headers={"X-Forwarded-For": "3.3.3.3"},
                )
                self.assertEqual(r3.status_code, 429)
                self.assertEqual(r3.get_json().get("error"), "rate_limited")
        finally:
            ctrl.flow_mgr.stop()

    def test_hosted_blocks_apply_policy_flag(self):
        flags = resolve_request_safety_flags(
            {"demo_mode": False, "allow_containment_in_demo": True, "apply_policy": True, "apply_gate": False}
        )
        os.environ["SDN_HOSTED_DEMO"] = "1"
        os.environ["SDN_API_TOKEN"] = "judge-token-secure-01"
        flags = resolve_request_safety_flags(
            {"demo_mode": False, "allow_containment_in_demo": True, "apply_policy": True, "apply_gate": False}
        )
        self.assertTrue(flags["demo_mode"])
        self.assertFalse(flags["allow_containment_in_demo"])
        self.assertTrue(flags["apply_gate"])
        self.assertFalse(flags["apply_policy"])

    def test_authorized_offline_multistep_and_of_mock(self):
        os.environ["SDN_API_TOKEN"] = "judge-token-secure-01"
        ctrl = self._ctrl()
        try:
            c = ctrl.app.test_client()
            r = c.post(
                "/api/v1/hackathon/multistep",
                json={"scenario_id": "scenario_rush_vs_attack", "mode": "offline", "demo_mode": False},
                headers={"X-API-Token": "judge-token-secure-01"},
            )
            self.assertEqual(r.status_code, 200)
            body = r.get_json()
            self.assertEqual(body.get("evidence_class"), "deterministic_planner")
            self.assertTrue(body.get("demo_mode"))
            self.assertEqual(body.get("of_backend"), "mock")
        finally:
            ctrl.flow_mgr.stop()

    def test_timeout_fail_closed(self):
        ctrl = self._ctrl()
        try:
            c = ctrl.app.test_client()
            with patch(
                "sdn_its.llm.multi_step.run_multi_step_investigation",
                side_effect=TimeoutError("nebius request timed out"),
            ):
                r = c.post(
                    "/api/v1/hackathon/multistep",
                    json={"scenario_id": "scenario_loft_stable", "mode": "real"},
                )
            self.assertEqual(r.status_code, 502)
            body = r.get_json()
            self.assertEqual(body.get("error"), "timeout")
            self.assertEqual((body.get("recommendation") or {}).get("recommended_action"), "observe")
        finally:
            ctrl.flow_mgr.stop()

    def test_malformed_rejected(self):
        ctrl = self._ctrl()
        try:
            c = ctrl.app.test_client()
            r = c.post(
                "/api/v1/hackathon/multistep",
                json={"mode": "offline", "telemetry": "bad"},
            )
            self.assertEqual(r.status_code, 400)
        finally:
            ctrl.flow_mgr.stop()

    def test_no_real_switch_containment_on_hosted_multistep(self):
        os.environ["SDN_HOSTED_DEMO"] = "1"
        os.environ["SDN_API_TOKEN"] = "judge-token-secure-01"
        os.environ["SDN_OF_BACKEND"] = "mock"
        from api.app import create_app

        app = create_app()
        c = app.test_client()
        r = c.post(
            "/api/v1/hackathon/multistep",
            json={
                "scenario_id": "scenario_loft_stable",
                "mode": "offline",
                "allow_containment_in_demo": True,
                "apply_policy": True,
            },
            headers={"X-API-Token": "judge-token-secure-01"},
        )
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertEqual(body.get("of_backend"), "mock")
        self.assertFalse(body.get("allow_containment_in_demo"))
        self.assertNotIn("policy", body)
        ctrl = app.extensions["sdn_controller"]
        self.assertFalse(ctrl.stats.get("network_evidence"))


class TestPolicyHelpers(unittest.TestCase):
    def tearDown(self):
        _clear_env("SDN_API_TOKEN", "SDN_HOSTED_DEMO")

    def test_token_forces_demo_policy(self):
        os.environ["SDN_API_TOKEN"] = "judge-token-secure-01"
        self.assertTrue(hosted_demo_enforced())
        demo, allow, notes = resolve_demo_policy(False, True)
        self.assertTrue(demo)
        self.assertFalse(allow)


if __name__ == "__main__":
    unittest.main()
