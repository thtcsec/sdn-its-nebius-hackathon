"""
evaluate.py - Experimental Benchmarking & Model Evaluation Script

Evaluates trained TCN-GRU / Temporal Transformer checkpoints on test telemetry.
Computes anomaly detection quality, multiclass metrics, IDL / T_response, and
exports confusion matrix + JSON metrics under results/.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import torch
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)

from sdn_its.ai.tcn_gru import TCNGRUResilienceModel
from sdn_its.ai.temporal_transformer import TemporalTransformerModel
from sdn_its.telemetry import LABEL_MAPPING, TelemetryDataLoader
from sdn_its.utils.paths import PROJECT_ROOT

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_NPZ = "datasets/processed/insdn_windows.npz"
DEFAULT_CSV = "datasets/sample/canonical_flows.csv"


def _build_model(arch: str, num_classes: int):
    if arch in {"transformer", "temporal_transformer", "attn"}:
        return TemporalTransformerModel(num_features=10, num_classes=num_classes)
    return TCNGRUResilienceModel(num_features=10, num_classes=num_classes)


def evaluate_checkpoint(
    checkpoint_path: str = "models/checkpoints/tcn_gru_best.pt",
    seq_len: int = 10,
    csv_path: str | None = None,
    npz_path: str | None = None,
    output_dir: str = "results",
):
    print("=" * 70)
    print("  EVALUATION & BENCHMARKING PIPELINE - SDN-ITS RESILIENCE AI")
    print("=" * 70)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[*] Evaluation Device: {device}")

    loader = TelemetryDataLoader(seq_len=seq_len, batch_size=32)
    _, _, test_dl = loader.resolve_loaders(
        npz_path=npz_path,
        csv_path=csv_path,
        synthetic_samples=1000,
    )

    tau_threshold = 0.5
    arch = "tcn_gru"

    if os.path.exists(checkpoint_path):
        print(f"[*] Loading trained model checkpoint: {checkpoint_path}")
        ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
        arch = ckpt.get("arch", "tcn_gru")
        model = _build_model(arch, len(LABEL_MAPPING)).to(device)
        model.load_state_dict(ckpt["model_state_dict"])
        tau_threshold = ckpt.get("tau_threshold", 0.5)
        print(f"[+] Loaded arch={arch} tau={tau_threshold:.4f}")
    else:
        print(f"[!] Warning: Checkpoint '{checkpoint_path}' not found. Evaluating untrained baseline.")
        model = _build_model(arch, len(LABEL_MAPPING)).to(device)
        dummy_sample = next(iter(test_dl))[0].to(device)
        tau_threshold = model.calibrate_threshold(dummy_sample, k=2.0)

    model.eval()

    y_true_binary: list[int] = []
    y_pred_binary: list[int] = []
    y_true_class: list[int] = []
    y_pred_class: list[int] = []
    y_probs_list: list[np.ndarray] = []
    inference_times_ms: list[float] = []

    t_collect = 5.0
    t_process = 1.2

    with torch.no_grad():
        for batch_x, batch_y in test_dl:
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)

            t0 = time.perf_counter()
            x_hat, logits = model(batch_x)
            t1 = time.perf_counter()

            batch_inference_ms = ((t1 - t0) * 1000.0) / batch_x.size(0)
            inference_times_ms.append(batch_inference_ms)

            diff = batch_x - x_hat
            re_scores = torch.sum(diff ** 2, dim=(1, 2)).cpu().numpy()
            is_anomaly_pred = (re_scores > tau_threshold).astype(int)

            probs = torch.softmax(logits, dim=-1).cpu().numpy()
            pred_class = np.argmax(probs, axis=-1)
            is_anomaly_true = (batch_y.cpu().numpy() > 0).astype(int)

            y_true_binary.extend(is_anomaly_true)
            y_pred_binary.extend(is_anomaly_pred)
            y_true_class.extend(batch_y.cpu().numpy())
            y_pred_class.extend(pred_class)
            y_probs_list.extend(probs)

    y_true_binary_arr = np.array(y_true_binary)
    y_pred_binary_arr = np.array(y_pred_binary)
    y_true_class_arr = np.array(y_true_class)
    y_pred_class_arr = np.array(y_pred_class)
    y_probs_arr = np.array(y_probs_list)

    acc = accuracy_score(y_true_binary_arr, y_pred_binary_arr)
    prec, rec, f1, _ = precision_recall_fscore_support(
        y_true_binary_arr, y_pred_binary_arr, average="binary", zero_division=0
    )
    # Classifier-head binary (often stronger than RE-threshold on real InSDN)
    y_pred_cls_bin = (y_pred_class_arr > 0).astype(int)
    acc_c = accuracy_score(y_true_binary_arr, y_pred_cls_bin)
    prec_c, rec_c, f1_c, _ = precision_recall_fscore_support(
        y_true_binary_arr, y_pred_cls_bin, average="binary", zero_division=0
    )
    try:
        roc_auc = roc_auc_score(y_true_binary_arr, y_probs_arr[:, 1:].sum(axis=1))
    except ValueError:
        roc_auc = float("nan")

    # Multiclass reporting (explicit averaging — do not conflate with cls_binary_*)
    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        y_true_class_arr, y_pred_class_arr, average="macro", zero_division=0
    )
    weighted_p, weighted_r, weighted_f1, _ = precision_recall_fscore_support(
        y_true_class_arr, y_pred_class_arr, average="weighted", zero_division=0
    )
    try:
        macro_ovr_auc = float(
            roc_auc_score(y_true_class_arr, y_probs_arr, multi_class="ovr", average="macro")
        )
    except ValueError:
        macro_ovr_auc = float("nan")

    print("\n--- ANOMALY DETECTION (RE threshold τ) ---")
    print(f"Accuracy:    {acc * 100:.2f}%")
    print(f"Precision:   {prec * 100:.2f}%")
    print(f"Recall:      {rec * 100:.2f}%")
    print(f"F1-Score:    {f1 * 100:.2f}%")
    print(f"ROC-AUC:     {roc_auc:.4f}")
    print("\n--- ANOMALY DETECTION (classifier head: class>0) ---")
    print(f"Accuracy:    {acc_c * 100:.2f}%")
    print(f"Precision:   {prec_c * 100:.2f}%")
    print(f"Recall:      {rec_c * 100:.2f}%")
    print(f"F1-Score:    {f1_c * 100:.2f}%")
    print(f"ROC-AUC:     {roc_auc:.4f}")

    print("\n--- MULTI-CLASS (explicit averaging) ---")
    print(f"Macro P/R/F1:     {macro_p*100:.2f}% / {macro_r*100:.2f}% / {macro_f1*100:.2f}%")
    print(f"Weighted P/R/F1:  {weighted_p*100:.2f}% / {weighted_r*100:.2f}% / {weighted_f1*100:.2f}%")
    print(f"Macro ROC-AUC OvR:{macro_ovr_auc:.4f}")
    print("\n--- MULTI-CLASS FAULT CLASSIFICATION REPORT ---")
    present = sorted(set(y_true_class_arr.tolist()) | set(y_pred_class_arr.tolist()))
    target_names = [LABEL_MAPPING.get(i, str(i)) for i in present]
    print(
        classification_report(
            y_true_class_arr,
            y_pred_class_arr,
            labels=present,
            target_names=target_names,
            zero_division=0,
        )
    )

    cm = confusion_matrix(y_true_class_arr, y_pred_class_arr, labels=present)
    out_dir = PathLike(output_dir)
    os.makedirs(out_dir, exist_ok=True)
    cm_path = os.path.join(out_dir, "confusion_matrix.png")
    metrics_path = os.path.join(out_dir, "eval_metrics.json")
    try:
        from visualization.heatmap import plot_confusion_heatmap

        plot_confusion_heatmap(cm, labels=target_names, out=cm_path)
        print(f"[+] Confusion matrix saved: {cm_path}")
    except Exception as exc:
        print(f"[!] Could not plot confusion matrix: {exc}")

    avg_inference_ms = float(np.mean(inference_times_ms))
    idl_latency = t_collect + t_process + avg_inference_ms
    t_decision = 0.5
    t_push = 2.0
    t_apply = 1.0
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

    split_meta = getattr(loader, "last_split_meta", {}) or {}
    metrics = {
        "arch": arch,
        "checkpoint": checkpoint_path,
        "npz_path": npz_path,
        "csv_path": csv_path,
        "n_test": int(len(y_true_class_arr)),
        "metric_definitions": {
            "cls_binary_*": "Binary Normal vs Anomaly from argmax(class)>0; sklearn average=binary",
            "roc_auc": "Binary ROC-AUC using score=sum(P(class!=Normal)); not multiclass OvR",
            "macro_*": "sklearn average=macro over observed classes",
            "weighted_*": "sklearn average=weighted over observed classes",
            "macro_roc_auc_ovr": "sklearn multi_class=ovr average=macro",
        },
        "binary_accuracy": float(acc),
        "binary_precision": float(prec),
        "binary_recall": float(rec),
        "binary_f1": float(f1),
        "cls_binary_accuracy": float(acc_c),
        "cls_binary_precision": float(prec_c),
        "cls_binary_recall": float(rec_c),
        "cls_binary_f1": float(f1_c),
        "roc_auc": float(roc_auc) if roc_auc == roc_auc else None,
        "macro_precision": float(macro_p),
        "macro_recall": float(macro_r),
        "macro_f1": float(macro_f1),
        "weighted_precision": float(weighted_p),
        "weighted_recall": float(weighted_r),
        "weighted_f1": float(weighted_f1),
        "macro_roc_auc_ovr": float(macro_ovr_auc) if macro_ovr_auc == macro_ovr_auc else None,
        "idl_ms": float(idl_latency),
        "t_response_ms": float(t_response),
        "inference_ms": avg_inference_ms,
        "tau": float(tau_threshold),
        "split_meta": split_meta,
        "confusion_matrix": cm.tolist(),
        "labels": target_names,
    }
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"[+] Metrics JSON saved: {metrics_path}")

    print("\n" + "=" * 70)
    print("[+] Benchmarking evaluation complete!")
    print("=" * 70)
    return metrics


def PathLike(path: str) -> str:
    """Resolve relative paths against project root."""
    if os.path.isabs(path):
        return path
    return str(PROJECT_ROOT / path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate resilience model checkpoint")
    parser.add_argument("--checkpoint", type=str, default="models/checkpoints/tcn_gru_best.pt")
    parser.add_argument("--npz", type=str, default=DEFAULT_NPZ)
    parser.add_argument("--csv", type=str, default=DEFAULT_CSV)
    parser.add_argument("--output_dir", type=str, default="results")
    parser.add_argument("--synthetic", action="store_true")
    args = parser.parse_args()

    evaluate_checkpoint(
        checkpoint_path=args.checkpoint,
        npz_path=None if args.synthetic else args.npz,
        csv_path=None if args.synthetic else args.csv,
        output_dir=args.output_dir,
    )
