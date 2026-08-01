"""Core SDN Resilience Controller composing FlowRuleManager + PolicyEngine + Flask app."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from sdn_its.controller.flow_manager import FlowRuleManager
from sdn_its.controller.of_backend import backend_status, resolve_of_backend
from sdn_its.mitigation.containment import FlowRule
from sdn_its.mitigation.policy_engine import PolicyEngine
from sdn_its.utils.alerts import AlertNotifier

if TYPE_CHECKING:
    from flask import Flask


class ResilienceSDNController:
    """Core SDN Controller Management Component."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        app: Flask | None = None,
        create_flask: bool = True,
        of_backend: str | None = None,
    ):
        self.host = host
        self.port = port
        self.of_backend_name, of_cb = resolve_of_backend(of_backend)
        self.flow_mgr = FlowRuleManager(
            rollback_check_interval=2.0,
            of_push_callback=of_cb,
        )
        self._of_callback = of_cb
        self.policy = PolicyEngine(self.flow_mgr.containment)
        self.stats: dict[str, Any] = {
            "total_alerts_received": 0,
            "mitigations_applied": 0,
            "false_positives_avoided": 0,
            "infer_calls": 0,
            "webhook_events": 0,
            "of_backend": self.of_backend_name,
            "start_time": time.time(),
        }
        self.runtime_settings: dict[str, Any] = {
            "tau": 53.12,
            "k_sigma": 2.0,
            "ddos_cooldown": 12.0,
            "loft_cooldown": 15.0,
            "poll_ms": 1200,
            "ambient_re": True,
            "auto_refresh": True,
            "adapt_tau": True,
            "dataset_mode": "sample",
            "role_mode": "research",
            "theme": "light",
            "compare_mode": False,
            "webhook_url": "",
            "webhook_enabled": False,
        }
        self.notifier = AlertNotifier()
        self.latency_samples_ms: list[float] = []
        self.app = app
        if self.app is not None:
            self.app.extensions["sdn_controller"] = self
        elif create_flask:
            from api.app import create_app

            self.app = create_app(controller=self)

    def _mock_openflow_switch_push(self, action: str, rule: FlowRule):
        """Backward-compatible alias — prefer of_backend.resolve_of_backend."""
        print(
            f"[OpenFlow Switch Channel] {action} Rule [{rule.rule_id}] -> "
            f"DPID={rule.dpid}, Match={rule.src_ip}, Action={rule.action}"
        )

    def openflow_status(self) -> dict[str, Any]:
        st = backend_status(self._of_callback)
        st["configured_backend"] = self.of_backend_name
        return st

    def update_runtime_settings(self, patch: dict[str, Any]) -> dict[str, Any]:
        allowed = set(self.runtime_settings.keys())
        for k, v in (patch or {}).items():
            if k in allowed:
                self.runtime_settings[k] = v
        if "tau" in patch:
            try:
                from sdn_its.ai.live_scorer import get_live_scorer

                get_live_scorer().set_tau(float(patch["tau"]))
            except Exception:
                pass
        if "k_sigma" in patch:
            try:
                from sdn_its.ai.live_scorer import get_live_scorer

                get_live_scorer().set_k_sigma(float(patch["k_sigma"]))
            except Exception:
                pass
        if "dataset_mode" in patch:
            try:
                from sdn_its.ai.live_scorer import get_live_scorer

                get_live_scorer().set_dataset_mode(str(patch["dataset_mode"]))
            except Exception:
                pass
        if "webhook_url" in patch or "webhook_enabled" in patch:
            self.notifier.configure(
                webhook_url=self.runtime_settings.get("webhook_url"),
                enabled=bool(self.runtime_settings.get("webhook_enabled")),
            )
        return dict(self.runtime_settings)

    def handle_alert(self, data: dict[str, Any]) -> dict[str, Any]:
        """Apply Detect -> Contain -> Rollback policy for an anomaly alert payload."""
        t0 = time.perf_counter()
        self.stats["total_alerts_received"] += 1
        alert_id = data.get("alert_id", f"ALT-{int(time.time())}")
        dpid = data["dpid"]
        src_ip = data.get("src_ip", "10.0.0.15")
        dst_ip = data.get("dst_ip")
        attack_type = data["attack_type"]
        default_cd = float(self.runtime_settings.get("ddos_cooldown", 30.0))
        if "LOFT" in attack_type:
            default_cd = float(self.runtime_settings.get("loft_cooldown", 15.0))
        cooldown = float(data.get("cooldown_seconds", default_cd))

        print(f"\n[ALERT RECEIVED] [{alert_id}] Type: {attack_type} | DPID: {dpid} | Src: {src_ip}")

        result = self.policy.apply(
            attack_type=attack_type,
            dpid=dpid,
            src_ip=src_ip,
            dst_ip=dst_ip,
            cooldown=cooldown,
        )

        if result.applied_rules:
            self.stats["mitigations_applied"] += 1
        if result.false_positive_avoided:
            self.stats["false_positives_avoided"] += 1

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self.latency_samples_ms.append(elapsed_ms)
        if len(self.latency_samples_ms) > 500:
            self.latency_samples_ms = self.latency_samples_ms[-500:]

        payload = {
            "status": "SUCCESS",
            "alert_id": alert_id,
            "mitigation_status": result.mitigation_status,
            "applied_rules_count": len(result.applied_rules),
            "applied_rules": result.applied_rules,
            "cooldown_seconds": cooldown,
            "policy_latency_ms": round(elapsed_ms, 3),
        }

        if result.applied_rules or result.false_positive_avoided:
            self.stats["webhook_events"] += 1
            self.notifier.notify(
                {
                    "alert_id": alert_id,
                    "attack_type": attack_type,
                    "mitigation_status": result.mitigation_status,
                    "rules": len(result.applied_rules),
                    "src_ip": src_ip,
                }
            )
        return payload

    def run(self, debug: bool = False):
        if self.app is None:
            from api.app import create_app

            self.app = create_app(controller=self)
        print(f"[*] Starting SDN Resilience Controller REST API on {self.host}:{self.port}...")
        self.app.run(host=self.host, port=self.port, debug=debug, use_reloader=False)
