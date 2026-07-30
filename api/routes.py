"""Flask route registration for dashboard + REST API."""

from __future__ import annotations

import time

from flask import Flask, jsonify, render_template, request

from api.schemas import status_payload, validate_anomaly_alert
from sdn_its.utils.paths import PROJECT_ROOT


def _load_runtime_settings(controller=None) -> dict:
    """Merge configs/*.yaml into a dashboard-friendly settings payload."""
    out = {
        "project": {"name": "sdn-its-resilience-ai", "version": "0.2.0"},
        "controller": {
            "host": "0.0.0.0",
            "port": 8080,
            "rollback_check_interval": 2.0,
            "default_cooldown_seconds": 30.0,
        },
        "telemetry": {"seq_len": 10, "num_features": 10, "poll_interval_ms": 5.0},
        "model": {
            "k_sigma": 2.0,
            "tcn_channels": [32, 64],
            "gru_hidden_dim": 64,
            "num_classes": 5,
            "dropout": 0.2,
        },
        "dataset": {
            "default_train_csv": "datasets/sample/canonical_flows.csv",
            "raw_insdn": "datasets/raw/insdn",
            "modes": ["sample", "synthetic", "insdn"],
        },
        "console_defaults": {
            "poll_ms": 1200,
            "tau": 53.12,
            "ddos_cooldown": 12.0,
            "loft_cooldown": 15.0,
            "ambient_re": True,
            "auto_refresh": True,
            "adapt_tau": True,
            "dataset_mode": "sample",
            "role_mode": "research",
            "theme": "light",
            "compare_mode": False,
            "webhook_url": "",
            "webhook_enabled": False,
        },
        "features": {
            "live_infer": True,
            "online_tau": True,
            "replay": True,
            "export_report": True,
            "onnx": True,
            "attribution": True,
            "webhooks": True,
        },
    }
    try:
        from sdn_its.utils.config import load_config

        for name in ("default", "controller", "dataset", "train", "alerts"):
            try:
                cfg = load_config(name)
            except Exception:
                continue
            if name == "default":
                out["project"].update(cfg.get("project") or {})
                out["telemetry"].update(cfg.get("telemetry") or {})
                out["model"].update(cfg.get("model") or {})
            elif name == "controller":
                out["controller"].update(cfg or {})
            elif name == "dataset":
                paths = (cfg or {}).get("paths") or {}
                out["dataset"]["default_train_csv"] = paths.get(
                    "default_train_csv", out["dataset"]["default_train_csv"]
                )
                out["dataset"]["raw_insdn"] = paths.get(
                    "raw_insdn", out["dataset"]["raw_insdn"]
                )
                schema = (cfg or {}).get("schema") or {}
                if "seq_len" in schema:
                    out["telemetry"]["seq_len"] = schema["seq_len"]
            elif name == "train" and cfg.get("k_sigma") is not None:
                out["model"]["k_sigma"] = cfg["k_sigma"]
            elif name == "alerts":
                out["console_defaults"]["webhook_url"] = cfg.get("webhook_url", "")
                out["console_defaults"]["webhook_enabled"] = bool(cfg.get("enabled", False))
    except Exception:
        pass

    if controller is not None:
        out["controller"]["port"] = getattr(controller, "port", out["controller"]["port"])
        out["controller"]["host"] = getattr(controller, "host", out["controller"]["host"])
        runtime = getattr(controller, "runtime_settings", None) or {}
        out["runtime"] = dict(runtime)
        out["console_defaults"].update({k: runtime[k] for k in runtime if k in out["console_defaults"]})
        try:
            from sdn_its.ai.live_scorer import get_live_scorer

            scorer = get_live_scorer()
            out["scorer"] = scorer.status()
            out["console_defaults"]["tau"] = scorer.status()["tau"]
        except Exception:
            out["scorer"] = {"loaded": False}
        out["alerts"] = controller.notifier.status()
    return out


_REPLAY_SCRIPTS = {
    "ddos_cycle": [
        {"t": 0, "scenario": "normal", "label": "Baseline"},
        {"t": 2, "scenario": "ddos", "label": "Flood onset", "alert": True},
        {"t": 8, "scenario": "ddos", "label": "Contain window"},
        {"t": 14, "scenario": "normal", "label": "Cooldown / rollback"},
    ],
    "loft_cycle": [
        {"t": 0, "scenario": "normal", "label": "Baseline"},
        {"t": 2, "scenario": "loft", "label": "LOFT probe", "alert": True},
        {"t": 10, "scenario": "normal", "label": "Rate-limit expire"},
    ],
    "rush_compare": [
        {"t": 0, "scenario": "rush_hour", "label": "Rush-hour (policy ignore)", "alert": True},
        {"t": 3, "scenario": "ddos", "label": "Same volume as attack", "alert": True},
    ],
    "full_story": [
        {"t": 0, "scenario": "normal", "label": "Nominal V2X"},
        {"t": 3, "scenario": "ddos", "label": "PacketIn flood", "alert": True},
        {"t": 9, "scenario": "loft", "label": "LOFT follow-up", "alert": True},
        {"t": 15, "scenario": "rush_hour", "label": "Rush-hour preserve", "alert": True},
        {"t": 20, "scenario": "normal", "label": "Recovered"},
    ],
}


def register_routes(app: Flask) -> None:
    @app.route("/", methods=["GET"])
    def index():
        return render_template("index.html")

    @app.route("/api/v1/status", methods=["GET"])
    def status():
        controller = app.extensions["sdn_controller"]
        return jsonify(status_payload(controller)), 200

    @app.route("/api/v1/settings", methods=["GET", "POST"])
    def settings():
        controller = app.extensions.get("sdn_controller")
        if request.method == "POST":
            if controller is None:
                return jsonify({"error": "controller unavailable"}), 503
            data = request.get_json(force=True, silent=True) or {}
            runtime = controller.update_runtime_settings(data)
            return jsonify({"status": "ok", "runtime": runtime, "settings": _load_runtime_settings(controller)}), 200
        return jsonify(_load_runtime_settings(controller)), 200

    @app.route("/api/v1/active_rules", methods=["GET"])
    def get_active_rules():
        controller = app.extensions["sdn_controller"]
        return jsonify(
            {
                "count": len(controller.flow_mgr.active_rules),
                "active_rules": controller.flow_mgr.get_all_active_rules(),
            }
        ), 200

    @app.route("/api/v1/rollback_history", methods=["GET"])
    def get_rollback_history():
        controller = app.extensions["sdn_controller"]
        return jsonify(
            {
                "count": len(controller.flow_mgr.rollback_history),
                "history": controller.flow_mgr.rollback_history,
            }
        ), 200

    @app.route("/api/v1/anomaly_alert", methods=["POST"])
    def handle_anomaly_alert():
        controller = app.extensions["sdn_controller"]
        data = request.get_json(force=True, silent=True)
        ok, err = validate_anomaly_alert(data)
        if not ok:
            return jsonify({"error": err}), 400
        return jsonify(controller.handle_alert(data)), 200

    @app.route("/api/v1/infer", methods=["POST", "GET"])
    def infer_live():
        from sdn_its.ai.live_scorer import get_live_scorer

        controller = app.extensions.get("sdn_controller")
        scorer = get_live_scorer()
        if request.method == "GET":
            scenario = request.args.get("scenario", "normal")
            adapt = request.args.get("adapt_tau", "1") not in ("0", "false", "False")
            auto = request.args.get("auto_alert", "0") in ("1", "true", "True")
            data = {}
        else:
            data = request.get_json(force=True, silent=True) or {}
            scenario = data.get("scenario", "normal")
            adapt = bool(data.get("adapt_tau", True))
            auto = bool(data.get("auto_alert", False))

        result = scorer.score(window=data.get("window"), scenario=scenario, adapt_tau=adapt)
        if controller is not None:
            controller.stats["infer_calls"] = controller.stats.get("infer_calls", 0) + 1
            controller.runtime_settings["tau"] = result["threshold_tau"]
            if result.get("latency_ms") is not None:
                controller.latency_samples_ms.append(float(result["latency_ms"]))

        alert_result = None
        if auto and result.get("is_anomaly") and result.get("attack_type") not in ("Normal", "RushHour_Burst"):
            if controller is not None:
                alert_result = controller.handle_alert(
                    {
                        "alert_id": f"INF-{int(time.time())}",
                        "dpid": data.get("dpid", "0000000000000001"),
                        "src_ip": data.get("src_ip", "10.0.0.15"),
                        "attack_type": result["attack_type"],
                        "reconstruction_error": result["reconstruction_error"],
                        "confidence": 0.9,
                    }
                )
        result["alert"] = alert_result
        return jsonify(result), 200

    @app.route("/api/v1/telemetry", methods=["GET"])
    def telemetry_tick():
        """Ambient live score for dashboard RE chart."""
        from sdn_its.ai.live_scorer import get_live_scorer

        scenario = request.args.get("scenario", "normal")
        result = get_live_scorer().score(scenario=scenario, adapt_tau=True)
        return jsonify(result), 200

    @app.route("/api/v1/replay", methods=["GET", "POST"])
    def replay():
        if request.method == "GET":
            return jsonify({"scripts": list(_REPLAY_SCRIPTS.keys()), "detail": _REPLAY_SCRIPTS}), 200
        data = request.get_json(force=True, silent=True) or {}
        name = data.get("script", "ddos_cycle")
        script = _REPLAY_SCRIPTS.get(name)
        if not script:
            return jsonify({"error": f"unknown script '{name}'", "available": list(_REPLAY_SCRIPTS)}), 400
        return jsonify({"script": name, "steps": script, "duration_s": script[-1]["t"] + 2}), 200

    @app.route("/api/v1/replay/step", methods=["POST"])
    def replay_step():
        """Execute one replay step: score (+ optional alert)."""
        from sdn_its.ai.live_scorer import get_live_scorer

        controller = app.extensions["sdn_controller"]
        data = request.get_json(force=True, silent=True) or {}
        scenario = data.get("scenario", "normal")
        do_alert = bool(data.get("alert", False))
        result = get_live_scorer().score(scenario=scenario, adapt_tau=(scenario == "normal"))
        alert_out = None
        if do_alert:
            cooldown = controller.runtime_settings.get("ddos_cooldown", 12.0)
            if "LOFT" in result["attack_type"]:
                cooldown = controller.runtime_settings.get("loft_cooldown", 15.0)
            if result["attack_type"] == "RushHour_Burst":
                cooldown = 0.0
            alert_out = controller.handle_alert(
                {
                    "alert_id": f"REP-{int(time.time() * 1000) % 100000}",
                    "dpid": "0000000000000001",
                    "src_ip": data.get("src_ip", "10.0.0.15"),
                    "attack_type": result["attack_type"],
                    "reconstruction_error": result["reconstruction_error"],
                    "confidence": 0.95,
                    "cooldown_seconds": cooldown,
                }
            )
        return jsonify({"score": result, "alert": alert_out, "label": data.get("label")}), 200

    @app.route("/api/v1/latency_cdf", methods=["GET"])
    def latency_cdf():
        controller = app.extensions["sdn_controller"]
        samples = list(controller.latency_samples_ms)
        if not samples:
            return jsonify({"count": 0, "percentiles": {}, "samples": []}), 200
        import numpy as np

        arr = np.sort(np.asarray(samples, dtype=float))
        pcts = {p: float(np.percentile(arr, p)) for p in (50, 90, 95, 99)}
        return jsonify(
            {
                "count": len(arr),
                "mean_ms": float(arr.mean()),
                "percentiles": pcts,
                "samples": arr[-100:].tolist(),
            }
        ), 200

    @app.route("/api/v1/export/report", methods=["POST"])
    def export_report():
        from sdn_its.ai.live_scorer import get_live_scorer
        from sdn_its.ai.report import write_markdown_report

        controller = app.extensions["sdn_controller"]
        data = request.get_json(force=True, silent=True) or {}
        name = data.get("name", f"console_report_{int(time.time())}")
        out_rel = data.get("path", f"results/{name}.md")
        metrics = {
            "alerts": controller.stats.get("total_alerts_received"),
            "mitigations": controller.stats.get("mitigations_applied"),
            "fp_avoided": controller.stats.get("false_positives_avoided"),
            "infer_calls": controller.stats.get("infer_calls"),
            "active_rules": len(controller.flow_mgr.active_rules),
            "tau": get_live_scorer().status()["tau"],
            "latency_n": len(controller.latency_samples_ms),
        }
        if controller.latency_samples_ms:
            import numpy as np

            arr = np.asarray(controller.latency_samples_ms)
            metrics["latency_p50_ms"] = float(np.percentile(arr, 50))
            metrics["latency_p95_ms"] = float(np.percentile(arr, 95))
        path = write_markdown_report(metrics, out_rel, title="SDN-ITS Console Snapshot")
        return jsonify({"status": "ok", "path": str(path.relative_to(PROJECT_ROOT))}), 200

    @app.route("/api/v1/export/onnx", methods=["POST"])
    def export_onnx_route():
        from sdn_its.ai.export_onnx import export_onnx, export_torchscript

        data = request.get_json(force=True, silent=True) or {}
        fmt = data.get("format", "onnx")
        results = {}
        try:
            if fmt in ("onnx", "both"):
                results["onnx"] = export_onnx()
            if fmt in ("torchscript", "both"):
                results["torchscript"] = export_torchscript()
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500
        return jsonify({"status": "ok", "exports": results}), 200

    @app.route("/api/v1/topology", methods=["GET"])
    def topology():
        """Mock topology health derived from active rules (OVS hook point)."""
        controller = app.extensions["sdn_controller"]
        rules = controller.flow_mgr.get_all_active_rules()
        containing = len(rules) > 0
        nodes = {
            "s1": {"role": "core", "dpid": "…0001", "state": "containing" if containing else "nominal"},
            "s2": {"role": "rsu", "state": "nominal"},
            "s3": {"role": "rsu", "state": "nominal"},
            "s4": {"role": "rsu", "state": "nominal"},
            "ctrl": {"role": "controller", "state": "active"},
        }
        return jsonify({"nodes": nodes, "active_rules": len(rules), "note": "stub — wire ovs-ofctl stats"}), 200
