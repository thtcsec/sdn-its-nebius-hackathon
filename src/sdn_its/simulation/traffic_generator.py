import argparse
import random
import time

import requests


class LiveTrafficSimulator:
    """
    Continuous synthetic telemetry → controller /api/v1/infer (auto_alert).

    Important: inference must go through the controller so infer_calls, inference_id,
    and policy_decision_id stay correlated. Local torch bypass caused infer_calls=0
    while mitigations climbed — that contradiction is intentional to avoid.
    """

    def __init__(self, controller_url: str = "http://127.0.0.1:8080"):
        self.controller_url = controller_url.rstrip("/")

    def generate_feature_sample(self, scenario: str) -> list:
        """Generates a 10-dimensional feature vector simulating RSU telemetry."""
        if scenario == "NORMAL":
            return [
                random.uniform(0.1, 2.0),
                random.uniform(5.0, 20.0),
                random.uniform(2.0, 10.0),
                random.uniform(1.0, 5.0),
                random.uniform(0.01, 0.05),
                random.uniform(0.001, 0.01),
                random.uniform(64, 128),
                random.uniform(5, 20),
                random.uniform(0.5, 2.0),
                random.uniform(0.0, 0.1),
            ]
        if scenario == "DDOS":
            return [
                random.uniform(5.0, 15.0),
                random.uniform(150.0, 300.0),
                random.uniform(100.0, 200.0),
                random.uniform(50.0, 100.0),
                random.uniform(0.001, 0.005),
                random.uniform(0.0001, 0.001),
                random.uniform(40, 64),
                random.uniform(0, 5),
                random.uniform(50.0, 120.0),
                random.uniform(0.8, 1.0),
            ]
        if scenario == "LOFT":
            return [
                random.uniform(10.0, 30.0),
                random.uniform(15.0, 30.0),
                random.uniform(10.0, 25.0),
                random.uniform(5.0, 12.0),
                random.uniform(0.08, 0.15),
                random.uniform(0.02, 0.08),
                random.uniform(100, 300),
                random.uniform(30, 80),
                random.uniform(8.0, 18.0),
                random.uniform(0.2, 0.4),
            ]
        # RUSH_HOUR
        return [
            random.uniform(0.5, 3.0),
            random.uniform(40.0, 80.0),
            random.uniform(30.0, 60.0),
            random.uniform(15.0, 30.0),
            random.uniform(0.01, 0.04),
            random.uniform(0.005, 0.02),
            random.uniform(128, 512),
            random.uniform(20, 50),
            random.uniform(3.0, 6.0),
            random.uniform(0.01, 0.05),
        ]

    def run_continuous_stream(self, interval: float = 1.5):
        print("=" * 70)
        print("  TELEMETRY → /api/v1/infer (correlated policy path)")
        print("=" * 70)
        print(f"[*] Streaming to {self.controller_url} every {interval}s...")

        scenarios = ["NORMAL", "NORMAL", "NORMAL", "RUSH_HOUR", "NORMAL", "DDOS", "NORMAL", "LOFT", "NORMAL"]
        gt_map = {
            "NORMAL": "Normal",
            "DDOS": "DDoS_PacketIn_Flood",
            "LOFT": "LOFT_LowRate_Attack",
            "RUSH_HOUR": "RushHour_Burst",
        }
        src_ip_map = {
            "DDOS": "10.0.0.15",
            "LOFT": "10.0.0.18",
            "RUSH_HOUR": "10.0.0.12",
            "NORMAL": "10.0.0.99",
        }
        # Rolling window of L=10 feature vectors (server also accepts single-step via scenario)
        window: list[list[float]] = []
        idx = 0

        try:
            while True:
                current_scenario = scenarios[idx % len(scenarios)]
                feat = self.generate_feature_sample(current_scenario)
                window.append(feat)
                if len(window) > 10:
                    window = window[-10:]

                # Warm-up until full window
                if len(window) < 10:
                    idx += 1
                    time.sleep(interval)
                    continue

                sc_api = {
                    "NORMAL": "normal",
                    "DDOS": "ddos",
                    "LOFT": "loft",
                    "RUSH_HOUR": "rush",
                }[current_scenario]

                payload = {
                    "window": window,
                    "scenario": sc_api,
                    "adapt_tau": current_scenario == "NORMAL",
                    "auto_alert": True,
                    "force_alert": current_scenario in ("DDOS", "LOFT", "RUSH_HOUR"),
                    "ground_truth": gt_map[current_scenario],
                    "dpid": "0000000000000001",
                    "src_ip": src_ip_map[current_scenario],
                    "window_id": f"STR-{int(time.time() * 1000) % 10_000_000}",
                }

                try:
                    r = requests.post(
                        f"{self.controller_url}/api/v1/infer",
                        json=payload,
                        timeout=2.0,
                    )
                    body = r.json() if r.ok else {}
                    re_score = body.get("reconstruction_error")
                    pred = body.get("predicted_label") or body.get("attack_type")
                    mode = body.get("mode") or "?"
                    iid = body.get("inference_id")
                    alert = body.get("alert") or {}
                    pol = alert.get("policy_decision_id") or "—"
                    act = alert.get("actuation_state") or "no_alert"
                    print(
                        f"[{time.strftime('%H:%M:%S')}] {current_scenario:<10} | "
                        f"mode={mode} RE={re_score} pred={pred} "
                        f"inf={iid} pol={pol} act={act}"
                    )
                except Exception as exc:
                    print(f"[{time.strftime('%H:%M:%S')}] stream error: {exc}")

                idx += 1
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n[*] Telemetry streaming stopped by user.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live V2X Telemetry Streamer (via /infer)")
    parser.add_argument("--controller", type=str, default="http://127.0.0.1:8080")
    parser.add_argument("--interval", type=float, default=1.5)
    args = parser.parse_args()

    sim = LiveTrafficSimulator(controller_url=args.controller)
    sim.run_continuous_stream(interval=args.interval)


# Backward-compatible alias
V2XTrafficGenerator = LiveTrafficSimulator
