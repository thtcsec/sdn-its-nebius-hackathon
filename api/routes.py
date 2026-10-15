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
            "host": "127.0.0.1",
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
        """Hackathon product home — JunctionTrace investigator (not the research console)."""
        return render_template("junctiontrace.html")

    @app.route("/research", methods=["GET"])
    def research_console():
        """Preserved IEDE / SDN research dashboard (pre-existing lab UI)."""
        return render_template("index.html")

    @app.route("/api/v1/hackathon/capabilities", methods=["GET"])
    def hackathon_capabilities():
        """Non-secret capability flags for the product UI (never returns API keys)."""
        from sdn_its.utils.env import nebius_config_summary

        cfg = nebius_config_summary()
        return jsonify(
            {
                "product": "JunctionTrace",
                "nebius_api_key_present": bool(cfg.get("nebius_api_key_present")),
                "nebius_model": cfg.get("nebius_model") or "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
                "of_backend_default": "mock",
                "camera_label": "synthetic_metadata_only",
                "modes": ["offline", "real"],
                "note": (
                    "Offline uses a deterministic planner. Real mode calls Nebius Token Factory "
                    "only when NEBIUS_API_KEY is configured server-side."
                ),
            }
        ), 200

    @app.route("/api/v1/status", methods=["GET"])
    def status():
        controller = app.extensions["sdn_controller"]
        return jsonify(status_payload(controller)), 200

    @app.route("/api/v1/lab", methods=["GET"])
    def lab_status():
        """Lab / OpenFlow agent snapshot + recent mitigation OF results."""
        controller = app.extensions["sdn_controller"]
        return jsonify(controller.lab_snapshot()), 200

    @app.route("/api/v1/lab/evidence", methods=["GET"])
    def lab_evidence():
        """Traffic / Detection / Actuation / Outcome board (+ Exp A file if present)."""
        from sdn_its.lab.evidence import build_evidence_board

        controller = app.extensions["sdn_controller"]
        return jsonify(build_evidence_board(controller)), 200

    @app.route("/api/v1/camera", methods=["GET"])
    def camera_status():
        from sdn_its.camera.store import get_camera_store

        return jsonify(get_camera_store().snapshot()), 200

    @app.route("/api/v1/camera/<camera_id>/preview", methods=["GET"])
    def camera_preview(camera_id: str):
        """Serve the single overwritten JPEG for a camera (no archive / no video)."""
        from flask import send_file

        from sdn_its.camera.store import get_camera_store

        path = get_camera_store().latest_frame_path(camera_id)
        if path is None:
            return jsonify({"error": "preview_unavailable", "camera_id": camera_id}), 404
        resp = send_file(path, mimetype="image/jpeg", max_age=2, conditional=True)
        resp.headers["Cache-Control"] = "no-store, max-age=0"
        return resp

    @app.route("/api/v1/camera/reload", methods=["POST"])
    def camera_reload():
        """Reload allow-list from configs/cameras.yaml (no env sprawl)."""
        from sdn_its.camera.store import get_camera_store

        store = get_camera_store(reload=True)
        return jsonify({"status": "ok", "snapshot": store.snapshot()}), 200

    @app.route("/api/v1/camera/scenario", methods=["POST"])
    def camera_scenario():
        from sdn_its.camera.store import get_camera_store

        data = request.get_json(force=True, silent=True) or {}
        scenario = str(data.get("scenario") or "idle")
        store = get_camera_store()
        store.set_scenario(scenario)
        return jsonify({"status": "ok", "scenario": store.get_scenario(), "aggregate": store.aggregate_context()}), 200

    @app.route("/api/v1/camera/fusion_preview", methods=["POST"])
    def camera_fusion_preview():
        """Dry-run fusion without installing rules — for decision panel / demos."""
        from sdn_its.camera.fusion import FusionEngine
        from sdn_its.camera.store import get_camera_store

        data = request.get_json(force=True, silent=True) or {}
        store = get_camera_store()
        if data.get("camera_scenario"):
            store.set_scenario(str(data["camera_scenario"]))
        physical = store.aggregate_context()
        net = str(data.get("network_prediction") or data.get("attack_type") or "Normal")
        dominance = float(data.get("source_dominance", 0.5))
        decision = FusionEngine().fuse(
            network_prediction=net,
            physical=physical,
            source_dominance=dominance,
            distributed_sources=data.get("distributed_sources", dominance < 0.45),
            packet_in_delta_pct=data.get("packet_in_delta_pct"),
        )
        out = decision.to_dict()
        out["physical"] = physical
        return jsonify(out), 200

    @app.route("/api/v1/empirical", methods=["GET"])
    def empirical_metrics():
        from sdn_its.ai.empirical import load_empirical_metrics

        return jsonify(load_empirical_metrics()), 200

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
        raw = controller.flow_mgr.get_all_active_rules()
        rules = (
            controller.annotate_rules(raw)
            if hasattr(controller, "annotate_rules")
            else raw
        )
        evidence = (
            controller.network_evidence_available()
            if hasattr(controller, "network_evidence_available")
            else False
        )
        return jsonify(
            {
                "count": len(rules),
                "intended_rules_count": len(rules),
                "network_evidence": evidence,
                "actuation_note": (
                    "switch_verified"
                    if evidence
                    else "in_memory_intended — NOT verified on switch (mock/disconnected)"
                ),
                "active_rules": rules,
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

        allow_override = True
        if controller is not None:
            allow_override = controller.allow_scenario_override()
        result = scorer.score(
            window=data.get("window"),
            scenario=scenario,
            adapt_tau=adapt,
            allow_scenario_override=allow_override,
            allow_simulation_fallback=allow_override,
        )
        window_id = data.get("window_id") or f"WIN-{int(time.time() * 1000) % 10_000_000}"
        inference_id = result.get("inference_id") or f"INF-{window_id}"
        result["window_id"] = window_id
        result["inference_id"] = inference_id
        if controller is not None:
            controller.stats["infer_calls"] = controller.stats.get("infer_calls", 0) + 1
            controller.runtime_settings["tau"] = result["threshold_tau"]
            if result.get("latency_ms") is not None:
                samples = getattr(controller, "infer_latency_samples_ms", None)
                if samples is None:
                    samples = controller.latency_samples_ms
                samples.append(float(result["latency_ms"]))
                if len(samples) > 500:
                    del samples[:-500]

        alert_result = None
        # auto_alert: policy on anomaly OR rush-hour (preserve path) OR explicit force
        force_alert = bool(data.get("force_alert", False))
        attack = result.get("attack_type") or "Normal"
        should_alert = auto and (
            force_alert
            or result.get("is_anomaly")
            or attack == "RushHour_Burst"
            or (allow_override and attack != "Normal")
        )
        if should_alert and attack != "Normal" and controller is not None:
            cooldown = controller.runtime_settings.get("ddos_cooldown", 12.0)
            if "LOFT" in str(attack):
                cooldown = controller.runtime_settings.get("loft_cooldown", 15.0)
            if attack == "RushHour_Burst":
                cooldown = 0.0
            alert_result = controller.handle_alert(
                {
                    "alert_id": f"INF-{int(time.time() * 1000) % 100000}",
                    "window_id": window_id,
                    "inference_id": inference_id,
                    "dpid": data.get("dpid", "0000000000000001"),
                    "src_ip": data.get("src_ip", "10.0.0.15"),
                    "attack_type": attack,
                    "prediction": result.get("predicted_label") or attack,
                    "ground_truth": data.get("ground_truth") or result.get("ground_truth"),
                    "reconstruction_error": result["reconstruction_error"],
                    "confidence": float(result.get("confidence") or 0.9),
                    "cooldown_seconds": cooldown,
                }
            )
        result["alert"] = alert_result
        result["lab_mode"] = bool((controller.runtime_settings if controller else {}).get("lab_mode"))
        return jsonify(result), 200

    @app.route("/api/v1/telemetry", methods=["GET"])
    def telemetry_tick():
        """Ambient live score for dashboard RE chart."""
        from sdn_its.ai.live_scorer import get_live_scorer

        controller = app.extensions.get("sdn_controller")
        scenario = request.args.get("scenario", "normal")
        allow_override = True
        if controller is not None:
            allow_override = controller.allow_scenario_override()
        result = get_live_scorer().score(
            scenario=scenario,
            adapt_tau=True,
            allow_scenario_override=allow_override,
            allow_simulation_fallback=allow_override,
        )
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
        allow_override = controller.allow_scenario_override()
        result = get_live_scorer().score(
            scenario=scenario,
            adapt_tau=(scenario == "normal"),
            allow_scenario_override=allow_override,
            allow_simulation_fallback=allow_override,
        )
        alert_out = None
        attack_type = result.get("attack_type")
        if do_alert and isinstance(attack_type, str) and attack_type:
            # In lab mode only alert when model/classifier says anomaly
            if allow_override or result.get("is_anomaly") or attack_type != "Normal":
                cooldown = controller.runtime_settings.get("ddos_cooldown", 12.0)
                if "LOFT" in attack_type:
                    cooldown = controller.runtime_settings.get("loft_cooldown", 15.0)
                if attack_type == "RushHour_Burst":
                    cooldown = 0.0
                if attack_type != "Normal" or allow_override:
                    wid = f"REP-WIN-{int(time.time() * 1000) % 100000}"
                    iid = f"REP-INF-{wid}"
                    result["window_id"] = wid
                    result["inference_id"] = iid
                    controller.stats["infer_calls"] = controller.stats.get("infer_calls", 0) + 1
                    if result.get("latency_ms") is not None:
                        getattr(controller, "infer_latency_samples_ms", controller.latency_samples_ms).append(
                            float(result["latency_ms"])
                        )
                    alert_out = controller.handle_alert(
                        {
                            "alert_id": f"REP-{int(time.time() * 1000) % 100000}",
                            "window_id": wid,
                            "inference_id": iid,
                            "dpid": "0000000000000001",
                            "src_ip": data.get("src_ip", "10.0.0.15"),
                            "attack_type": attack_type,
                            "prediction": result.get("predicted_label") or attack_type,
                            "ground_truth": data.get("ground_truth") or result.get("ground_truth"),
                            "reconstruction_error": result["reconstruction_error"],
                            "confidence": 0.95,
                            "cooldown_seconds": cooldown,
                        }
                    )
        return jsonify({"score": result, "alert": alert_out, "label": data.get("label")}), 200

    @app.route("/api/v1/latency_cdf", methods=["GET"])
    def latency_cdf():
        controller = app.extensions["sdn_controller"]
        kind = (request.args.get("kind") or "policy").lower()
        if kind in ("infer", "inference", "model"):
            samples = list(getattr(controller, "infer_latency_samples_ms", []) or [])
            latency_kind = "inference_in_process"
        elif kind in ("all", "mixed"):
            # Explicit mixed — avoid accidental overclaim
            samples = list(getattr(controller, "policy_latency_samples_ms", controller.latency_samples_ms) or [])
            samples = samples + list(getattr(controller, "infer_latency_samples_ms", []) or [])
            latency_kind = "mixed_policy_and_infer_NOT_e2e"
        else:
            samples = list(getattr(controller, "policy_latency_samples_ms", controller.latency_samples_ms) or [])
            latency_kind = "policy_in_process"
        note = (
            "In-process software timing only. Not switch install latency, "
            "not PacketIn→mitigation E2E, not ITS network RTT."
        )
        if not samples:
            return jsonify(
                {
                    "count": 0,
                    "percentiles": {},
                    "samples": [],
                    "kind": kind,
                    "latency_kind": latency_kind,
                    "note": note,
                }
            ), 200
        import numpy as np

        arr = np.sort(np.asarray(samples, dtype=float))
        pcts = {p: float(np.percentile(arr, p)) for p in (50, 90, 95, 99)}
        return jsonify(
            {
                "count": len(arr),
                "mean_ms": float(arr.mean()),
                "percentiles": pcts,
                "samples": arr[-100:].tolist(),
                "kind": kind,
                "latency_kind": latency_kind,
                "note": note,
            }
        ), 200

    @app.route("/api/v1/export/report", methods=["GET", "POST"])
    def export_report():
        """Preview (GET) or write+download metadata (POST) for console Markdown report."""
        from sdn_its.ai.report import build_console_report_markdown, write_console_report

        controller = app.extensions["sdn_controller"]
        if request.method == "GET":
            markdown, metrics = build_console_report_markdown(controller)
            return jsonify(
                {
                    "status": "ok",
                    "preview": True,
                    "markdown": markdown,
                    "metrics": metrics,
                    "filename": f"console_preview_{int(time.time())}.md",
                }
            ), 200

        data = request.get_json(force=True, silent=True) or {}
        name = data.get("name", f"console_{int(time.time())}")
        # sanitize filename segment
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(name))[:80]
        out_rel = data.get("path", f"results/console/{safe}.md")
        path, markdown, metrics = write_console_report(controller, out_rel)
        rel = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
        return jsonify(
            {
                "status": "ok",
                "path": rel,
                "filename": path.name,
                "markdown": markdown,
                "metrics": metrics,
                "download_url": f"/api/v1/export/report/file?path={rel}",
            }
        ), 200

    @app.route("/api/v1/export/report/file", methods=["GET"])
    def export_report_file():
        """Download a report written under results/ (path query, relative to project root)."""
        from flask import send_file

        rel = (request.args.get("path") or "").replace("\\", "/").lstrip("/")
        if not rel.startswith("results/") or ".." in rel or rel.endswith("/"):
            return jsonify({"error": "invalid path — must be under results/"}), 400
        path = (PROJECT_ROOT / rel).resolve()
        try:
            path.relative_to((PROJECT_ROOT / "results").resolve())
        except ValueError:
            return jsonify({"error": "path escapes results/"}), 400
        if not path.is_file():
            return jsonify({"error": f"file not found: {rel}"}), 404
        return send_file(path, as_attachment=True, download_name=path.name)

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

    @app.route("/api/v1/hackathon/investigate", methods=["POST"])
    def hackathon_investigate():
        """Nemotron investigation vertical slice (Nebius Token Factory).

        Requires NEBIUS_API_KEY for real_api evidence. Never fabricates success.
        Demo mode blocks containment intentions by default.
        """
        from sdn_its.llm.investigation import IncidentContext, investigate_incident
        from sdn_its.llm.audit_log import record_audit
        from sdn_its.utils.env import ensure_repo_env

        ensure_repo_env()
        data = request.get_json(force=True, silent=True) or {}
        demo_mode = bool(data.get("demo_mode", True))
        allow_containment = bool(data.get("allow_containment_in_demo", False))
        ctx = IncidentContext(
            network_prediction=str(data.get("network_prediction") or "Normal"),
            telemetry=dict(data.get("telemetry") or {}),
            camera=dict(data.get("camera") or {}),
            rule_fusion=data.get("rule_fusion"),
            dpid=str(data.get("dpid") or "1"),
            src_ip=str(data.get("src_ip") or "10.0.0.15"),
        )
        result = investigate_incident(
            ctx,
            demo_mode=demo_mode,
            allow_containment_in_demo=allow_containment,
            model=data.get("model"),
        )
        payload = result.to_dict()
        payload["of_backend"] = getattr(app.extensions["sdn_controller"], "of_backend_name", "mock")
        payload["note"] = (
            "Advisory investigation only. Deterministic PolicyEngine remains authoritative; "
            "default OF backend is mock unless SDN_OF_BACKEND is set."
        )
        record_audit(
            {
                "source": "api_investigate",
                "network_prediction": ctx.network_prediction,
                "nemotron_action": (result.recommendation.recommended_action if result.recommendation else None),
                "nemotron_evidence_class": result.evidence_class,
                "gated_notes": result.gated_notes,
                "ok": result.ok,
            }
        )
        if result.evidence_class == "blocked_no_credentials":
            return jsonify(payload), 503
        if not result.ok:
            return jsonify(payload), 502
        # Optionally map through policy without claiming switch evidence
        if data.get("apply_policy") and result.fusion_for_policy is not None:
            controller = app.extensions["sdn_controller"]
            mit = controller.policy.apply(
                attack_type=ctx.network_prediction,
                dpid=ctx.dpid,
                src_ip=ctx.src_ip,
                fusion=result.fusion_for_policy,
            )
            payload["policy"] = {
                "mitigation_status": mit.mitigation_status,
                "applied_rules_count": len(mit.applied_rules),
                "network_evidence": bool(controller.stats.get("network_evidence")),
            }
        return jsonify(payload), 200

    @app.route("/api/v1/hackathon/incidents", methods=["GET"])
    def hackathon_incidents():
        from sdn_its.llm.fixtures import incident_summaries
        from sdn_its.llm.scenarios import scenario_summaries

        return jsonify(
            {
                "incidents": incident_summaries(),
                "scenarios": scenario_summaries(),
                "camera": "synthetic_metadata_only",
                "note": "Scenarios demonstrate multi-step investigation; camera is fixture metadata not live RTSP.",
            }
        ), 200

    @app.route("/api/v1/hackathon/run", methods=["POST"])
    def hackathon_run_incident():
        """Run rule-only + Nemotron-assisted paths for a fixture/scenario id or inline body."""
        from sdn_its.llm.agent import investigate_case
        from sdn_its.llm.fixtures import load_incident

        data = request.get_json(force=True, silent=True) or {}
        mode = str(data.get("mode") or "offline")
        if mode not in {"offline", "real"}:
            return jsonify({"error": "mode must be offline|real"}), 400
        demo_mode = bool(data.get("demo_mode", True))
        multi_step = bool(data.get("multi_step", False))
        if data.get("scenario_id"):
            from sdn_its.llm.scenarios import load_scenario

            try:
                incident = load_scenario(str(data["scenario_id"]))
            except FileNotFoundError:
                return jsonify({"error": f"unknown scenario_id {data['scenario_id']}"}), 404
            multi_step = True
        elif data.get("incident_id"):
            try:
                incident = load_incident(f"{data['incident_id']}.json")
            except FileNotFoundError:
                # allow bare id match
                from sdn_its.llm.fixtures import load_all_incidents

                hits = [i for i in load_all_incidents() if i["id"] == data["incident_id"]]
                if not hits:
                    # try scenario id
                    from sdn_its.llm.scenarios import load_scenario

                    try:
                        incident = load_scenario(str(data["incident_id"]))
                        multi_step = True
                    except FileNotFoundError:
                        return jsonify({"error": f"unknown incident_id {data['incident_id']}"}), 404
                else:
                    incident = hits[0]
        else:
            incident = {
                "id": data.get("id") or "inline",
                "title": data.get("title") or "inline",
                "network_prediction": data.get("network_prediction") or "Normal",
                "telemetry": data.get("telemetry") or {},
                "camera": data.get("camera") or {},
                "dpid": data.get("dpid") or "1",
                "src_ip": data.get("src_ip") or "10.0.0.15",
                "synthetic_model_output": data.get("synthetic_model_output"),
                "force_mode": data.get("force_mode"),
                "synthetic_model_output_raw": data.get("synthetic_model_output_raw"),
                "expected": data.get("expected") or {},
            }
        case = investigate_case(
            incident,
            mode=mode,  # type: ignore[arg-type]
            demo_mode=demo_mode,
            allow_containment_in_demo=bool(data.get("allow_containment_in_demo", False)),
            multi_step=multi_step,
        )
        payload = case.to_dict()
        payload["of_backend"] = getattr(app.extensions["sdn_controller"], "of_backend_name", "mock")
        payload["multi_step"] = multi_step
        if multi_step and isinstance((payload.get("nemotron") or {}).get("fusion"), dict):
            payload["investigation_trace"] = payload["nemotron"]["fusion"].get("trace")
        return jsonify(payload), 200

    @app.route("/api/v1/hackathon/multistep", methods=["POST"])
    def hackathon_multistep():
        """Explicit multi-step investigation with full trace (mock OF)."""
        from sdn_its.llm.agent import run_rule_only
        from sdn_its.llm.audit_log import record_audit
        from sdn_its.llm.multi_step import run_multi_step_investigation
        from sdn_its.llm.scenarios import load_scenario

        data = request.get_json(force=True, silent=True) or {}
        mode = str(data.get("mode") or "offline")
        if mode not in {"offline", "real"}:
            return jsonify({"error": "mode must be offline|real"}), 400
        sid = data.get("scenario_id") or data.get("incident_id")
        if sid:
            try:
                incident = load_scenario(str(sid))
            except FileNotFoundError:
                from sdn_its.llm.fixtures import load_all_incidents

                hits = [i for i in load_all_incidents() if i["id"] == sid]
                if not hits:
                    return jsonify({"error": f"unknown id {sid}"}), 404
                incident = hits[0]
        else:
            incident = {
                "id": data.get("id") or "inline",
                "network_prediction": data.get("network_prediction") or "Normal",
                "telemetry": data.get("telemetry") or {},
                "camera": data.get("camera") or {},
            }
        rule = run_rule_only(incident)
        ms = run_multi_step_investigation(
            incident,
            mode=mode,  # type: ignore[arg-type]
            include_camera=bool(data.get("include_camera", True)),
            apply_gate=bool(data.get("apply_gate", True)),
            demo_mode=bool(data.get("demo_mode", True)),
            allow_containment_in_demo=bool(data.get("allow_containment_in_demo", False)),
            rule_fusion=rule.fusion,
        )
        payload = ms.to_dict()
        payload["rule"] = rule.to_dict()
        payload["of_backend"] = getattr(app.extensions["sdn_controller"], "of_backend_name", "mock")
        payload["product_story"] = (
            "A network traffic surge is not always an attack. "
            "Investigate physical context before making disruptive decisions."
        )
        record_audit(
            {
                "source": "api_multistep",
                "incident_id": incident.get("id"),
                "action": (ms.recommendation.recommended_action if ms.recommendation else None),
                "evidence_class": ms.evidence_class,
                "tool_calls": ms.tool_calls,
                "gated_notes": ms.gated_notes,
                "trace": [t.to_dict() for t in ms.trace],
            }
        )
        return jsonify(payload), 200 if ms.ok else 502

    @app.route("/api/v1/hackathon/audit", methods=["GET"])
    def hackathon_audit():
        from sdn_its.llm.audit_log import list_audit

        limit = request.args.get("limit", 40, type=int)
        return jsonify({"audit": list_audit(limit=limit or 40)}), 200

