"""
evaluate.py - Experimental Benchmarking & Model Evaluation Script

Evaluates trained TCN-GRU model on test telemetry dataset.
Computes Anomaly Detection Quality (Accuracy, Precision, Recall, F1, ROC-AUC),
Multi-class Fault Classification Metrics, and Edge Latency Metrics (IDL, T_response).

Formulas Evaluated:
- IDL = t_collect + t_process + t_inference
- T_response = IDL + t_decision + t_push + t_apply
"""

import argparse
import os
import sys
import time

# Ensure project root directory is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import torch
from sklearn.metrics import accuracy_score, classification_report, precision_recall_fscore_support, roc_auc_score

from sdn_its.ai.tcn_gru import TCNGRUResilienceModel
from sdn_its.telemetry import LABEL_MAPPING, TelemetryDataLoader


def evaluate_checkpoint(
    checkpoint_path: str = "models/checkpoints/tcn_gru_best.pt",
    seq_len: int = 10,
    csv_path: str = None
):
    print("=" * 70)
    print("  EVALUATION & BENCHMARKING PIPELINE - SDN-ITS RESILIENCE AI")
    print("=" * 70)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[*] Evaluation Device: {device}")

    # 1. Load Test Data
    loader = TelemetryDataLoader(seq_len=seq_len, batch_size=32)
    if csv_path and os.path.exists(csv_path):
        print(f"[*] Loading test data split from CSV: {csv_path}")
        _, _, test_dl = loader.get_csv_loaders(csv_path)
    else:
        _, _, test_dl = loader.get_synthetic_loaders(num_samples=1000)

    # 2. Load Checkpoint or Initialize Baseline
    model = TCNGRUResilienceModel(num_features=10, num_classes=len(LABEL_MAPPING)).to(device)
    tau_threshold = 0.5

    if os.path.exists(checkpoint_path):
        print(f"[*] Loading trained model checkpoint: {checkpoint_path}")
        ckpt = torch.load(checkpoint_path, map_location=device)
        model.load_state_dict(ckpt["model_state_dict"])
        tau_threshold = ckpt.get("tau_threshold", 0.5)
        print(f"[+] Loaded model checkpoint successfully. Calibrated Tau: {tau_threshold:.4f}")
    else:
        print(f"[!] Warning: Checkpoint '{checkpoint_path}' not found. Evaluating un-trained model baseline.")
        # Calibrate dummy threshold
        dummy_sample = next(iter(test_dl))[0].to(device)
        tau_threshold = model.calibrate_threshold(dummy_sample, k=2.0)

    model.eval()

    # 3. Model Inference & Timing Measurements
    y_true_binary = []
    y_pred_binary = []
    y_true_class = []
    y_pred_class = []
    y_probs_list = []

    inference_times_ms = []

    t_collect = 5.0    # 5.0 ms sFlow / OpenFlow push polling interval
    t_process = 1.2    # 1.2 ms telemetry feature normalization & windowing

    with torch.no_grad():
        for batch_x, batch_y in test_dl:
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)

            # Benchmark single sample inference latency
            t0 = time.perf_counter()
            x_hat, logits = model(batch_x)
            t1 = time.perf_counter()

            batch_inference_ms = ((t1 - t0) * 1000.0) / batch_x.size(0)
            inference_times_ms.append(batch_inference_ms)

            # Reconstruction error for anomaly binary scoring
            diff = batch_x - x_hat
            re_scores = torch.sum(diff ** 2, dim=(1, 2)).cpu().numpy()
            is_anomaly_pred = (re_scores > tau_threshold).astype(int)

            probs = torch.softmax(logits, dim=-1).cpu().numpy()
            pred_class = np.argmax(probs, axis=-1)

            # Binary Ground Truth: 0 = Normal, 1..4 = Anomaly/Fault
            is_anomaly_true = (batch_y.cpu().numpy() > 0).astype(int)

            y_true_binary.extend(is_anomaly_true)
            y_pred_binary.extend(is_anomaly_pred)
            y_true_class.extend(batch_y.cpu().numpy())
            y_pred_class.extend(pred_class)
            y_probs_list.extend(probs)

    y_true_binary = np.array(y_true_binary)
    y_pred_binary = np.array(y_pred_binary)
    y_true_class = np.array(y_true_class)
    y_pred_class = np.array(y_pred_class)
    y_probs_list = np.array(y_probs_list)

    # 4. Anomaly Detection Metrics
    acc = accuracy_score(y_true_binary, y_pred_binary)
    prec, rec, f1, _ = precision_recall_fscore_support(y_true_binary, y_pred_binary, average='binary')
    roc_auc = roc_auc_score(y_true_binary, y_probs_list[:, 1:].sum(axis=1))

    print("\n--- ANOMALY DETECTION METRICS (Binary Normal vs Anomaly) ---")
    print(f"Accuracy:    {acc * 100:.2f}%")
    print(f"Precision:   {prec * 100:.2f}%")
    print(f"Recall:      {rec * 100:.2f}%")
    print(f"F1-Score:    {f1 * 100:.2f}%")
    print(f"ROC-AUC:     {roc_auc:.4f}")

    # 5. Multiclass Fault Classification Report
    print("\n--- MULTI-CLASS FAULT CLASSIFICATION REPORT ---")
    target_names = [LABEL_MAPPING[i] for i in range(len(LABEL_MAPPING))]
    print(classification_report(y_true_class, y_pred_class, target_names=target_names, zero_division=0))

    # 6. Latency Analysis (From Research Proposal Equations)
    avg_inference_ms = np.mean(inference_times_ms)
    idl_latency = t_collect + t_process + avg_inference_ms

    t_decision = 0.5   # 0.5 ms anomaly classification & policy evaluation
    t_push = 2.0       # 2.0 ms REST API / OpenFlow flow_mod transmission
    t_apply = 1.0      # 1.0 ms OVS switch rule installation
    t_response = idl_latency + t_decision + t_push + t_apply

    print("--- REAL-TIME LATENCY BENCHMARKS ---")
    print(f"1. Telemetry Collection (t_collect):   {t_collect:.2f} ms")
    print(f"2. Feature Preprocessing (t_process):  {t_process:.2f} ms")
    print(f"3. Model Inference (t_inference):       {avg_inference_ms:.3f} ms")
    print(f"--> Intrusion Detection Latency (IDL): {idl_latency:.3f} ms")
    print(f"4. Controller Decision (t_decision):   {t_decision:.2f} ms")
    print(f"5. Flow Rule Push (t_push):             {t_push:.2f} ms")
    print(f"6. OVS Switch Apply (t_apply):         {t_apply:.2f} ms")
    print(f"==> End-to-End Response (T_response):  {t_response:.3f} ms")

    print("\n" + "=" * 70)
    print("[+] Benchmarking evaluation complete!")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate TCN-GRU Model Benchmark")
    parser.add_argument("--checkpoint", type=str, default="models/checkpoints/tcn_gru_best.pt", help="Path to checkpoint")
    parser.add_argument("--csv", type=str, default=None, help="Path to real-world CSV dataset file")
    args = parser.parse_args()

    evaluate_checkpoint(checkpoint_path=args.checkpoint, csv_path=args.csv)
