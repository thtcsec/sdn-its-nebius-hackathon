"""Core SDN Resilience Controller composing FlowRuleManager + PolicyEngine + Flask app."""

from __future__ import annotations

import time
from collections import deque
from typing import TYPE_CHECKING, Any

from sdn_its.controller.flow_manager import FlowRuleManager
from sdn_its.controller.of_backend import backend_status, resolve_of_backend
from sdn_its.mitigation.containment import FlowRule
from sdn_its.mitigation.policy_engine import PolicyEngine
from sdn_its.utils.alerts import AlertNotifier
from sdn_its.utils.security import is_loopback_bind, resolve_bind_host

if TYPE_CHECKING:
    from flask import Flask


class ResilienceSDNController:
    """Core SDN Controller Management Component."""

    def __init__(
        self,
        host: str | None = None,
        port: int = 8080,
        app: Flask | None = None,
        create_flask: bool = True,
        of_backend: str | None = None,
    ):
        self.host = resolve_bind_host(host)
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
            # Honest counters (aliases kept for older clients)
            "policy_decisions": 0,
            "mitigations_applied": 0,  # alias of policy_decisions that requested rules
            "rush_hour_policy_preserves": 0,
            "false_positives_avoided": 0,  # ONLY fusion-corrected FP (not label-only IGNORE)
            "fusion_preserves": 0,
            "fusion_contains": 0,
            "of_rules_installed": 0,  # only when OF backend ACKs
            "infer_calls": 0,  # controller /api/v1/infer only
            "client_side_infers": 0,  # streamer local torch (if reported)
            "webhook_events": 0,
            "of_backend": self.of_backend_name,
            "network_evidence": False,
            "start_time": time.time(),
            "bind_host": self.host,
            "loopback_only": is_loopback_bind(self.host),
        }
        self.last_fusion: dict[str, Any] | None = None
        self.policy_latency_samples_ms: deque[float] = deque(maxlen=500)
        self.infer_latency_samples_ms: deque[float] = deque(maxlen=500)
        self.event_trace: deque[dict[str, Any]] = deque(maxlen=200)
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
        # Backward-compat name used by latency_cdf — POLICY path only
        self.latency_samples_ms = self.policy_latency_samples_ms
        self.mitigation_log: deque[dict[str, Any]] = deque(maxlen=200)
        self.app = app
        self.stats["network_evidence"] = self.of_backend_name not in {"mock", ""}
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

    def network_evidence_available(self) -> bool:
        of = self.openflow_status(refresh=False)
        backend = (of.get("configured_backend") or of.get("backend") or self.of_backend_name or "mock").lower()
        if backend in {"mock"}:
            return False
        return bool(of.get("connected"))

    def annotate_rules(self, rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
        evidence = self.network_evidence_available()
        out = []
        for r in rules:
            row = dict(r)
            own = row.get("actuation_state") or (row.get("parameters") or {}).get("actuation", {}).get(
                "actuation_state"
            )
            if row.get("verified_in_flow_dump"):
                row["actuation_state"] = "switch_verified"
            elif own in {"switch_ack", "switch_verified", "push_failed"}:
                row["actuation_state"] = own
            else:
                row["actuation_state"] = "switch_verified" if evidence else "in_memory_intended"
            row["network_evidence"] = evidence or bool(row.get("verified_in_flow_dump"))
            out.append(row)
        return out

    def lab_snapshot(self) -> dict[str, Any]:
        of = self.openflow_status(refresh=True)
        evidence = self.network_evidence_available()
        self.stats["network_evidence"] = evidence
        return {
            "lab_mode": bool(self.runtime_settings.get("lab_mode")),
            "scenario_override": self.allow_scenario_override(),
            "of_backend": self.of_backend_name,
            "openflow": of,
            "agent_connected": bool(of.get("connected")),
            "network_evidence": evidence,
            "intended_rules_count": len(self.flow_mgr.active_rules),
            "active_rules": len(self.flow_mgr.active_rules),
            "mitigation_log": list(self.mitigation_log)[-40:],
            "event_trace": list(self.event_trace)[-40:],
            "stats": dict(self.stats),
            "latency_note": "policy_latency_ms is in-process policy timing, not switch install / E2E",
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
            status = self.notifier.configure(
                webhook_url=self.runtime_settings.get("webhook_url"),
                enabled=bool(self.runtime_settings.get("webhook_enabled")),
            )
            # Reflect SSRF rejection in runtime settings so the console stays honest
            if status.get("rejected_url"):
                self.runtime_settings["webhook_url"] = ""
                self.runtime_settings["webhook_enabled"] = False
                self.runtime_settings["webhook_error"] = status.get("reject_reason")
            else:
                self.runtime_settings.pop("webhook_error", None)
        return dict(self.runtime_settings)

    def handle_alert(self, data: dict[str, Any]) -> dict[str, Any]:
        """Apply Detect -> Contain -> Rollback policy for an anomaly alert payload."""
        t0 = time.perf_counter()
        self.stats["total_alerts_received"] += 1
        self.stats["policy_decisions"] = int(self.stats.get("policy_decisions", 0)) + 1
        alert_id = data.get("alert_id", f"ALT-{int(time.time())}")
        inference_id = data.get("inference_id") or data.get("window_id") or f"INF-EXT-{alert_id}"
        policy_decision_id = f"POL-{alert_id}"
        dpid = data["dpid"]
        src_ip = data.get("src_ip", "10.0.0.15")
        dst_ip = data.get("dst_ip")
        attack_type = data["attack_type"]
        prediction = data.get("prediction") or data.get("predicted_label")
        ground_truth = data.get("ground_truth")
        default_cd = float(self.runtime_settings.get("ddos_cooldown", 30.0))
        if "LOFT" in attack_type:
            default_cd = float(self.runtime_settings.get("loft_cooldown", 15.0))
        cooldown = float(data.get("cooldown_seconds", default_cd))

        print(f"\n[ALERT RECEIVED] [{alert_id}] Type: {attack_type} | DPID: {dpid} | Src: {src_ip}")

        # Multimodal fusion: SDN prediction × camera physical context
        fusion_dict: dict[str, Any] | None = None
        try:
            from sdn_its.camera.fusion import FusionEngine
            from sdn_its.camera.store import get_camera_store

            store = get_camera_store()
            if data.get("camera_scenario"):
                store.set_scenario(str(data["camera_scenario"]))
            physical = store.aggregate_context()
            dominance = data.get("source_dominance")
            if dominance is None:
                # Heuristic: single attacker IP demos → high dominance; rush scenarios lower
                dominance = 0.82 if "DDoS" in attack_type or "LOFT" in attack_type else 0.35
            distributed = data.get("distributed_sources")
            if distributed is None:
                distributed = float(dominance) < 0.45
            fusion = FusionEngine().fuse(
                network_prediction=str(prediction or attack_type),
                physical=physical,
                source_dominance=float(dominance),
                distributed_sources=bool(distributed),
                packet_in_delta_pct=data.get("packet_in_delta_pct"),
            )
            fusion_dict = fusion.to_dict()
            fusion_dict["physical"] = physical
            self.last_fusion = fusion_dict
            if fusion.cooldown_seconds is not None:
                cooldown = float(fusion.cooldown_seconds)
        except Exception as exc:  # noqa: BLE001
            fusion_dict = {"error": str(exc), "recommended_action": None}

        result = self.policy.apply(
            attack_type=attack_type,
            dpid=dpid,
            src_ip=src_ip,
            dst_ip=dst_ip,
            cooldown=cooldown,
            fusion=fusion_dict,
        )

        if result.applied_rules:
            self.stats["mitigations_applied"] += 1
            self.stats["fusion_contains"] = int(self.stats.get("fusion_contains", 0)) + 1
        if result.mitigation_status in {
            "IGNORED_BENIGN_RUSH_HOUR",
            "PROTECTED_SAFETY_CRITICAL",
            "OBSERVE_ONLY",
        }:
            self.stats["rush_hour_policy_preserves"] = (
                int(self.stats.get("rush_hour_policy_preserves", 0)) + 1
            )
            self.stats["fusion_preserves"] = int(self.stats.get("fusion_preserves", 0)) + 1
        if result.false_positive_avoided:
            # Only when fusion corrected anomaly → preserve (research FP metric)
            self.stats["false_positives_avoided"] += 1

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self.policy_latency_samples_ms.append(elapsed_ms)

        of_after = self.openflow_status(refresh=True)
        last_mods = list(of_after.get("last_mods") or [])
        evidence = self.network_evidence_available()
        self.stats["network_evidence"] = evidence
        of_installed = 0
        flow_mod_ids: list[str] = []
        if result.applied_rules and evidence:
            # Count ACKs from last mods when present; else treat connected http/ryu as installed
            acks = [m for m in last_mods if m.get("ok") is True]
            of_installed = len(acks) if acks else len(result.applied_rules)
            self.stats["of_rules_installed"] = int(self.stats.get("of_rules_installed", 0)) + of_installed
            flow_mod_ids = [str(m.get("cmd") or m.get("flow") or m.get("rule_id") or "mod") for m in last_mods[-of_installed:]]

        actuation = "switch_ack" if (result.applied_rules and evidence) else (
            "in_memory_intended" if result.applied_rules else "no_rule"
        )

        trace = {
            "ts": time.time(),
            "telemetry_window_id": data.get("window_id"),
            "inference_id": inference_id,
            "prediction": prediction,
            "ground_truth": ground_truth,
            "policy_decision_id": policy_decision_id,
            "alert_id": alert_id,
            "attack_type": attack_type,
            "mitigation_status": result.mitigation_status,
            "fusion": fusion_dict,
            "flow_mod_ids": flow_mod_ids,
            "switch_ack": evidence and bool(result.applied_rules),
            "actuation_state": actuation,
            "policy_latency_ms": round(elapsed_ms, 3),
            "of_backend": self.of_backend_name,
            "network_evidence": evidence,
            "note": None
            if evidence
            else "NO NETWORK EVIDENCE — rules are in-memory / mock unless SDN_OF_BACKEND=http|ryu",
        }
        self.event_trace.append(trace)

        payload = {
            "status": "SUCCESS",
            "alert_id": alert_id,
            "inference_id": inference_id,
            "policy_decision_id": policy_decision_id,
            "attack_type": attack_type,
            "prediction": prediction,
            "ground_truth": ground_truth,
            "mitigation_status": result.mitigation_status,
            "applied_rules_count": len(result.applied_rules),
            "applied_rules": result.applied_rules,
            "intended_rules_count": len(result.applied_rules),
            "of_rules_installed": of_installed,
            "actuation_state": actuation,
            "cooldown_seconds": cooldown,
            "policy_latency_ms": round(elapsed_ms, 3),
            "latency_kind": "policy_in_process",
            "of_backend": self.of_backend_name,
            "of_connected": bool(of_after.get("connected")),
            "network_evidence": evidence,
            "of_last_mods": last_mods[-3:],
            "fusion": fusion_dict,
            "trace": trace,
        }
        self.mitigation_log.append(
            {
                "ts": time.time(),
                "alert_id": alert_id,
                "inference_id": inference_id,
                "policy_decision_id": policy_decision_id,
                "attack_type": attack_type,
                "prediction": prediction,
                "ground_truth": ground_truth,
                "src_ip": src_ip,
                "mitigation_status": result.mitigation_status,
                "fusion_action": (fusion_dict or {}).get("recommended_action"),
                "physical_context": (fusion_dict or {}).get("physical_context"),
                "rules": result.applied_rules,
                "policy_latency_ms": round(elapsed_ms, 3),
                "of_backend": self.of_backend_name,
                "of_ok": bool(of_after.get("connected")) if result.applied_rules else None,
                "actuation_state": actuation,
                "network_evidence": evidence,
                "of_last_mods": last_mods[-2:],
            }
        )

        if result.applied_rules or result.false_positive_avoided:
            self.stats["webhook_events"] += 1
            self.notifier.notify(
                {
                    "alert_id": alert_id,
                    "attack_type": attack_type,
                    "mitigation_status": result.mitigation_status,
                    "rules": len(result.applied_rules),
                    "src_ip": src_ip,
                    "network_evidence": evidence,
                }
            )
        return payload

    def run(self, debug: bool = False):
        if self.app is None:
            from api.app import create_app

            self.app = create_app(controller=self)
        if not is_loopback_bind(self.host):
            print(
                f"[!] Binding {self.host}:{self.port} (LAN). "
                "Set SDN_API_TOKEN for mutating API auth; prefer SDN_BIND_HOST=127.0.0.1 for local demos."
            )
        print(f"[*] Starting SDN Resilience Controller REST API on http://{self.host}:{self.port}/ ...")
        self.app.run(host=self.host, port=self.port, debug=debug, use_reloader=False)
