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
            # Research-first defaults (demo inject requires turning Lab off)
            "ambient_re": False,
            "auto_refresh": True,
            "adapt_tau": True,
            "dataset_mode": "sample",
            "role_mode": "research",
            "theme": "research",
            "compare_mode": False,
            "webhook_url": "",
            "webhook_enabled": False,
            "lab_mode": True,
            "scenario_override": False,
        }
        self.notifier = AlertNotifier()
        self.latency_samples_ms: list[float] = []
        self.mitigation_log: list[dict[str, Any]] = []
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

    def openflow_status(self, *, refresh: bool = False) -> dict[str, Any]:
        st = backend_status(self._of_callback, refresh=refresh)
        st["configured_backend"] = self.of_backend_name
        return st

    def allow_scenario_override(self) -> bool:
        """Demo inject may force attack labels; Lab mode disables that."""
        if bool(self.runtime_settings.get("lab_mode")):
            return False
        return bool(self.runtime_settings.get("scenario_override", True))

    def lab_snapshot(self) -> dict[str, Any]:
        of = self.openflow_status(refresh=True)
        return {
            "lab_mode": bool(self.runtime_settings.get("lab_mode")),
            "scenario_override": self.allow_scenario_override(),
            "of_backend": self.of_backend_name,
            "openflow": of,
            "agent_connected": bool(of.get("connected")),
            "active_rules": len(self.flow_mgr.active_rules),
            "mitigation_log": list(self.mitigation_log)[-40:],
            "stats": dict(self.stats),
        }

    def update_runtime_settings(self, patch: dict[str, Any]) -> dict[str, Any]:
        patch = dict(patch or {})
        allowed = set(self.runtime_settings.keys())
        for k, v in patch.items():
            if k in allowed:
                self.runtime_settings[k] = v
        # Turning on lab_mode hard-disables scenario cheat + ambient fake RE by default
        if "lab_mode" in patch and bool(patch.get("lab_mode")):
            self.runtime_settings["scenario_override"] = False
            if "ambient_re" not in patch:
                self.runtime_settings["ambient_re"] = False
            if "theme" not in patch and self.runtime_settings.get("theme") == "light":
                self.runtime_settings["theme"] = "research"
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

        of_after = self.openflow_status(refresh=True)
        last_mods = list(of_after.get("last_mods") or [])
        payload = {
            "status": "SUCCESS",
            "alert_id": alert_id,
            "attack_type": attack_type,
            "mitigation_status": result.mitigation_status,
            "applied_rules_count": len(result.applied_rules),
            "applied_rules": result.applied_rules,
            "cooldown_seconds": cooldown,
            "policy_latency_ms": round(elapsed_ms, 3),
            "of_backend": self.of_backend_name,
            "of_connected": bool(of_after.get("connected")),
            "of_last_mods": last_mods[-3:],
        }
        self.mitigation_log.append(
            {
                "ts": time.time(),
                "alert_id": alert_id,
                "attack_type": attack_type,
                "src_ip": src_ip,
                "mitigation_status": result.mitigation_status,
                "rules": result.applied_rules,
                "policy_latency_ms": round(elapsed_ms, 3),
                "of_backend": self.of_backend_name,
                "of_ok": bool(of_after.get("connected")) if result.applied_rules else None,
                "of_last_mods": last_mods[-2:],
            }
        )
        if len(self.mitigation_log) > 200:
            self.mitigation_log = self.mitigation_log[-200:]

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
