import argparse
import os
import random
import sys
import time

import requests
import torch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sdn_its.ai.tcn_gru import TCNGRUResilienceModel
from sdn_its.telemetry import LABEL_MAPPING, StreamingTelemetryBuffer


class LiveTrafficSimulator:
    """
    Automated Continuous V2X Traffic & Telemetry Generator.
    Runs live PyTorch TCN-GRU inference on rolling telemetry buffers and posts dynamic alerts.
    """
    def __init__(self, controller_url: str = "http://127.0.0.1:8080", checkpoint_path: str = "models/checkpoints/tcn_gru_best.pt"):
        self.controller_url = controller_url
        self.stream_buf = StreamingTelemetryBuffer(seq_len=10, num_features=10)
        self.device = torch.device("cpu")

        # Load trained PyTorch Model
        self.model = TCNGRUResilienceModel(num_features=10, num_classes=len(LABEL_MAPPING))
        if os.path.exists(checkpoint_path):
            ckpt = torch.load(checkpoint_path, map_location=self.device)
            self.model.load_state_dict(ckpt["model_state_dict"])
            self.tau_threshold = ckpt.get("tau_threshold", 53.12)
            print(f"[+] Loaded PyTorch Model for Live Traffic Streaming. Tau = {self.tau_threshold:.2f}")
        else:
            self.tau_threshold = 53.12
            print("[!] Model checkpoint not found, using baseline threshold.")

        self.model.eval()

    def generate_feature_sample(self, scenario: str) -> list:
        """Generates a 10-dimensional feature vector simulating RSU telemetry."""
        if scenario == "NORMAL":
            return [
                random.uniform(0.1, 2.0),   # flow_duration
                random.uniform(5.0, 20.0),  # packet_rate
                random.uniform(2.0, 10.0),  # byte_rate
                random.uniform(1.0, 5.0),   # backward_pkt_rate
                random.uniform(0.01, 0.05), # iat_mean
                random.uniform(0.001, 0.01),# iat_std
                random.uniform(64, 128),    # pkt_len_mean
                random.uniform(5, 20),      # pkt_len_std
                random.uniform(0.5, 2.0),   # packet_in_freq
                random.uniform(0.0, 0.1)    # syn_flag_ratio
            ]
        elif scenario == "DDOS":
            return [
                random.uniform(5.0, 15.0),
                random.uniform(150.0, 300.0), # High packet rate
                random.uniform(100.0, 200.0),
                random.uniform(50.0, 100.0),
                random.uniform(0.001, 0.005),
                random.uniform(0.0001, 0.001),
                random.uniform(40, 64),
                random.uniform(0, 5),
                random.uniform(50.0, 120.0), # High PacketIn frequency
                random.uniform(0.8, 1.0)     # High SYN ratio
            ]
        elif scenario == "LOFT":
            return [
                random.uniform(10.0, 30.0),
                random.uniform(15.0, 30.0),
                random.uniform(10.0, 25.0),
                random.uniform(5.0, 12.0),
                random.uniform(0.08, 0.15),
                random.uniform(0.02, 0.08),
                random.uniform(100, 300),
                random.uniform(30, 80),
                random.uniform(8.0, 18.0),   # Moderate PacketIn pressure
                random.uniform(0.2, 0.4)
            ]
        else: # RUSH_HOUR
            return [
                random.uniform(0.5, 3.0),
                random.uniform(40.0, 80.0),  # High traffic, but benign
                random.uniform(30.0, 60.0),
                random.uniform(15.0, 30.0),
                random.uniform(0.01, 0.04),
                random.uniform(0.005, 0.02),
                random.uniform(128, 512),
                random.uniform(20, 50),
                random.uniform(3.0, 6.0),    # Low PacketIn ratio
                random.uniform(0.01, 0.05)
            ]

    def run_continuous_stream(self, interval: float = 1.5):
        print("=" * 70)
        print("  AUTOMATED REAL-TIME V2X TELEMETRY STREAMING DEMONSTRATOR")
        print("=" * 70)
        print(f"[*] Streaming live telemetry to Controller at {self.controller_url} every {interval}s...")

        scenarios = ["NORMAL", "NORMAL", "NORMAL", "RUSH_HOUR", "NORMAL", "DDOS", "NORMAL", "LOFT", "NORMAL"]
        idx = 0

        try:
            while True:
                current_scenario = scenarios[idx % len(scenarios)]
                feat = self.generate_feature_sample(current_scenario)

                # Push into rolling tensor buffer
                tensor_input = self.stream_buf.push(feat)

                # Model Inference
                with torch.no_grad():
                    x_hat, logits = self.model(tensor_input)
                    diff = tensor_input - x_hat
                    re_score = float(torch.sum(diff ** 2).item())
                    pred_class_idx = int(torch.argmax(logits, dim=1).item())

                label_names = list(LABEL_MAPPING.keys())
                pred_label = label_names[pred_class_idx] if pred_class_idx < len(label_names) else "Unknown"

                is_anomaly = re_score > self.tau_threshold
                status_str = f"ALERT (RE={re_score:.2f} > Tau)" if is_anomaly else f"NOMINAL (RE={re_score:.2f})"
                print(f"[{time.strftime('%H:%M:%S')}] Scenario: {current_scenario:<10} | {status_str:<25} | Class: {pred_label}")

                # Post alert if anomalous or rush hour
                if is_anomaly or current_scenario in ["DDOS", "LOFT", "RUSH_HOUR"]:
                    attack_type_map = {
                        "DDOS": "DDoS_PacketIn_Flood",
                        "LOFT": "LOFT_LowRate_Attack",
                        "RUSH_HOUR": "RushHour_Burst",
                        "NORMAL": "DDoS_PacketIn_Flood"
                    }

                    src_ip_map = {
                        "DDOS": "10.0.0.15",
                        "LOFT": "10.0.0.18",
                        "RUSH_HOUR": "10.0.0.12",
                        "NORMAL": "10.0.0.99"
                    }

                    payload = {
                        "alert_id": f"AUTO-{int(time.time())}",
                        "dpid": "0000000000000001",
                        "src_ip": src_ip_map[current_scenario],
                        "attack_type": attack_type_map[current_scenario],
                        "reconstruction_error": round(re_score, 2),
                        "confidence": 0.97,
                        "cooldown_seconds": 12.0
                    }

                    try:
                        requests.post(f"{self.controller_url}/api/v1/anomaly_alert", json=payload, timeout=1.0)
                    except Exception:
                        pass

                idx += 1
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n[*] Telemetry streaming stopped by user.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live V2X Telemetry Streamer")
    parser.add_argument("--controller", type=str, default="http://127.0.0.1:8080", help="Controller REST API URL")
    parser.add_argument("--interval", type=float, default=1.5, help="Streaming interval in seconds")
    args = parser.parse_args()

    sim = LiveTrafficSimulator(controller_url=args.controller)
    sim.run_continuous_stream(interval=args.interval)


# Backward-compatible alias
V2XTrafficGenerator = LiveTrafficSimulator
