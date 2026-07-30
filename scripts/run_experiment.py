#!/usr/bin/env python
"""Run a named experiment from experiments/*/config.yaml with metrics + report."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import _bootstrap  # noqa: F401
import numpy as np
import requests
import yaml

from sdn_its.ai.report import write_markdown_report
from sdn_its.utils.paths import PROJECT_ROOT

ATTACK_TO_TYPE = {
    "none": "Normal",
    "ddos": "DDoS_PacketIn_Flood",
    "loft": "LOFT_LowRate_Attack",
    "rush_hour": "RushHour_Burst",
}


def _post_alert(url: str, attack_type: str, re_score: float, cooldown: float) -> dict:
    payload = {
        "alert_id": f"EXP-{int(time.time() * 1000) % 1_000_000}",
        "dpid": "0000000000000001",
        "src_ip": "10.0.0.15" if "Rush" not in attack_type else "10.0.0.12",
        "attack_type": attack_type,
        "reconstruction_error": re_score,
        "confidence": 0.95,
        "cooldown_seconds": cooldown,
    }
    resp = requests.post(f"{url}/api/v1/anomaly_alert", json=payload, timeout=3)
    return {"http": resp.status_code, "body": resp.json()}


def _score(url: str, scenario: str) -> dict:
    try:
        resp = requests.get(f"{url}/api/v1/infer", params={"scenario": scenario}, timeout=5)
        return resp.json()
    except Exception as exc:
        return {"error": str(exc), "reconstruction_error": 0.0, "is_anomaly": False}


def run_experiment(cfg: dict, cfg_path: Path, dry_run: bool = False) -> dict:
    attack = cfg.get("attack", {})
    controller = cfg.get("controller", {})
    url = controller.get("url", "http://127.0.0.1:8080")
    attack_key = attack.get("type", "none")
    attack_type = ATTACK_TO_TYPE.get(attack_key, "DDoS_PacketIn_Flood")
    exp_id = cfg.get("experiment", {}).get("id", cfg_path.parent.name)
    out_dir = cfg_path.parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Experiment: {exp_id}")
    print(f"[*] Attack type: {attack_type} duration={attack.get('duration')} rate={attack.get('packet_rate')}")

    metrics = {
        "experiment_id": exp_id,
        "attack_type": attack_type,
        "duration_s": attack.get("duration", 0),
        "packet_rate": attack.get("packet_rate"),
        "dry_run": dry_run,
        "alerts_posted": 0,
        "rules_applied": 0,
        "fp_avoided": 0,
        "re_scores": [],
        "latencies_ms": [],
        "false_block": 0,
    }

    # DRL block for exp05
    drl_cfg = cfg.get("drl") or {}
    if drl_cfg.get("enabled"):
        from sdn_its.ai.drl_agent import DRLResilienceAgent

        agent = DRLResilienceAgent(tau_threshold=float(drl_cfg.get("tau", 53.12)))
        train_stats = agent.train_episodes(
            episodes=int(drl_cfg.get("episodes", 20)),
            steps_per_ep=int(drl_cfg.get("steps", 30)),
        )
        metrics["drl"] = train_stats
        ckpt = out_dir / "drl_agent.pt"
        agent.save(str(ckpt))
        metrics["drl_checkpoint"] = str(ckpt.relative_to(PROJECT_ROOT))
        print(f"[+] DRL trained: mean_reward={train_stats['mean_reward']:.2f}")

    if dry_run or attack_key in (None, "none"):
        # Baseline: collect normal RE ticks
        for _ in range(8):
            sc = _score(url, "normal")
            if "reconstruction_error" in sc:
                metrics["re_scores"].append(sc["reconstruction_error"])
                metrics["latencies_ms"].append(sc.get("latency_ms", 0))
        print("[+] Normal / dry-run — scored ambient windows only.")
    else:
        duration = int(attack.get("duration", 30))
        pulses = max(3, min(12, duration // 10))
        cooldown = float(controller.get("cooldown_seconds", 30))
        scenario = {"ddos": "ddos", "loft": "loft", "rush_hour": "rush_hour"}.get(attack_key, "ddos")

        for i in range(pulses):
            sc = _score(url, scenario)
            re_score = float(sc.get("reconstruction_error", 80.0))
            metrics["re_scores"].append(re_score)
            metrics["latencies_ms"].append(sc.get("latency_ms", 0))
            try:
                out = _post_alert(url, attack_type, re_score, cooldown if attack_key != "rush_hour" else 0.0)
                metrics["alerts_posted"] += 1
                body = out.get("body") or {}
                metrics["rules_applied"] += int(body.get("applied_rules_count", 0))
                if body.get("mitigation_status") == "IGNORED_BENIGN_RUSH_HOUR":
                    metrics["fp_avoided"] += 1
                if attack_key == "rush_hour" and int(body.get("applied_rules_count", 0)) > 0:
                    metrics["false_block"] += 1
                print(f"  pulse {i+1}/{pulses}: RE={re_score:.2f} → {body.get('mitigation_status')}")
            except Exception as exc:
                print(f"[!] Controller unreachable at {url}: {exc}")
                print("    Start demo first: python scripts/run_demo.py")
                metrics["error"] = str(exc)
                break
            time.sleep(0.35)

    if metrics["re_scores"]:
        arr = np.asarray(metrics["re_scores"], dtype=float)
        metrics["re_mean"] = float(arr.mean())
        metrics["re_max"] = float(arr.max())
    if metrics["latencies_ms"]:
        lat = np.asarray(metrics["latencies_ms"], dtype=float)
        metrics["infer_p50_ms"] = float(np.percentile(lat, 50))
        metrics["infer_p95_ms"] = float(np.percentile(lat, 95))

    # Compact summary without huge arrays in MD table
    summary = {k: v for k, v in metrics.items() if k not in ("re_scores", "latencies_ms")}
    summary["re_n"] = len(metrics["re_scores"])
    report = write_markdown_report(
        summary,
        out_dir / "report.md",
        title=f"Experiment {exp_id}",
        extra_sections={
            "Notes": (
                f"Attack `{attack_type}` · pulses posted={metrics['alerts_posted']} · "
                f"rules={metrics['rules_applied']} · FP avoided={metrics['fp_avoided']} · "
                f"false blocks={metrics['false_block']}"
            )
        },
    )
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str), encoding="utf-8")
    print(f"[+] Report → {report.relative_to(PROJECT_ROOT)}")
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exp", type=str, default=None, help="e.g. exp02_ddos")
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.config:
        cfg_path = Path(args.config)
    elif args.exp:
        cfg_path = PROJECT_ROOT / "experiments" / args.exp / "config.yaml"
    else:
        raise SystemExit("Provide --exp or --config")

    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    run_experiment(cfg, cfg_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
