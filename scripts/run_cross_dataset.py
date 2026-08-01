#!/usr/bin/env python
"""Cross-dataset holdout: train on InSDN windows, evaluate on CIC-IDS2017 windows.

Protocol:
  - Fit StandardScaler on train NPZ only
  - Transform holdout NPZ with that scaler (no leakage)
  - Score an existing checkpoint (default: TCN-GRU) with classifier-head metrics

Example:
  python scripts/run_cross_dataset.py \\
    --train-npz datasets/processed/insdn_windows.npz \\
    --test-npz datasets/processed/cic_windows.npz \\
    --checkpoint models/checkpoints/tcn_gru_best.pt
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import _bootstrap  # noqa: F401
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
from sdn_its.utils.paths import PROJECT_ROOT, ensure_dir


def _build_model(arch: str, num_classes: int):
    if arch in {"transformer", "temporal_transformer", "attn"}:
        return TemporalTransformerModel(num_features=10, num_classes=num_classes)
    return TCNGRUResilienceModel(num_features=10, num_classes=num_classes)


def run_cross_dataset(
    train_npz: str,
    test_npz: str,
    checkpoint: str,
    output_dir: str = "results/cross_dataset",
) -> dict:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    loader = TelemetryDataLoader(seq_len=10, batch_size=64)
    _, _, test_dl = loader.get_cross_dataset_loaders(train_npz, test_npz)

    if not Path(checkpoint).exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint}")

    ckpt = torch.load(checkpoint, map_location=device, weights_only=False)
    arch = ckpt.get("arch", "tcn_gru")
    model = _build_model(arch, len(LABEL_MAPPING)).to(device)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    tau = float(ckpt.get("tau_threshold", 0.5))

    y_true_bin, y_pred_re, y_pred_cls, y_true_cls, y_pred_mc, probs_list = [], [], [], [], [], []
    latencies = []

    with torch.no_grad():
        for batch_x, batch_y in test_dl:
            batch_x = batch_x.to(device)
            t0 = time.perf_counter()
            x_hat, logits = model(batch_x)
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000.0 / batch_x.size(0))

            re = torch.sum((batch_x - x_hat) ** 2, dim=(1, 2)).cpu().numpy()
            probs = torch.softmax(logits, dim=-1).cpu().numpy()
            pred_mc = np.argmax(probs, axis=-1)
            y_np = batch_y.numpy()

            y_true_bin.extend((y_np > 0).astype(int))
            y_pred_re.extend((re > tau).astype(int))
            y_pred_cls.extend((pred_mc > 0).astype(int))
            y_true_cls.extend(y_np)
            y_pred_mc.extend(pred_mc)
            probs_list.extend(probs)

    y_true_bin = np.array(y_true_bin)
    y_pred_cls = np.array(y_pred_cls)
    y_pred_re = np.array(y_pred_re)
    y_true_cls = np.array(y_true_cls)
    y_pred_mc = np.array(y_pred_mc)
    probs_arr = np.array(probs_list)

    acc = accuracy_score(y_true_bin, y_pred_cls)
    prec, rec, f1, _ = precision_recall_fscore_support(
        y_true_bin, y_pred_cls, average="binary", zero_division=0
    )
    acc_re = accuracy_score(y_true_bin, y_pred_re)
    try:
        roc = roc_auc_score(y_true_bin, probs_arr[:, 1:].sum(axis=1))
    except ValueError:
        roc = float("nan")

    present = sorted(set(y_true_cls.tolist()) | set(y_pred_mc.tolist()))
    names = [LABEL_MAPPING.get(i, str(i)) for i in present]
    report = classification_report(
        y_true_cls, y_pred_mc, labels=present, target_names=names, zero_division=0
    )
    cm = confusion_matrix(y_true_cls, y_pred_mc, labels=present)

    out = ensure_dir(PROJECT_ROOT / output_dir)
    try:
        from visualization.heatmap import plot_confusion_heatmap

        plot_confusion_heatmap(cm, labels=names, out=str(out / "confusion_matrix.png"))
    except Exception as exc:
        print(f"[!] confusion plot skipped: {exc}")

    metrics = {
        "protocol": "train_scaler_on_insdn_eval_on_cic",
        "train_npz": train_npz,
        "test_npz": test_npz,
        "checkpoint": checkpoint,
        "arch": arch,
        "n_test": int(len(y_true_bin)),
        "cls_binary_accuracy": float(acc),
        "cls_binary_precision": float(prec),
        "cls_binary_recall": float(rec),
        "cls_binary_f1": float(f1),
        "re_binary_accuracy": float(acc_re),
        "roc_auc": float(roc) if roc == roc else None,
        "inference_ms": float(np.mean(latencies)),
        "tau": tau,
        "confusion_matrix": cm.tolist(),
        "labels": names,
    }
    (out / "eval_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (out / "classification_report.txt").write_text(report, encoding="utf-8")

    print("=" * 70)
    print("  CROSS-DATASET HOLDOUT (InSDN → CIC)")
    print("=" * 70)
    print(f"Train NPZ: {train_npz}")
    print(f"Test  NPZ: {test_npz}")
    print(f"Arch/ckpt: {arch} | {checkpoint}")
    print(f"Holdout N: {metrics['n_test']}")
    print("\n--- Classifier-head binary ---")
    print(f"Accuracy  {acc * 100:.2f}%  Precision {prec * 100:.2f}%  "
          f"Recall {rec * 100:.2f}%  F1 {f1 * 100:.2f}%  ROC-AUC {roc:.4f}")
    print(f"RE-threshold accuracy (ref): {acc_re * 100:.2f}%")
    print("\n" + report)
    print(f"[+] Wrote {out / 'eval_metrics.json'}")
    return metrics


def main():
    parser = argparse.ArgumentParser(description="InSDN→CIC cross-dataset evaluation")
    parser.add_argument("--train-npz", default="datasets/processed/insdn_windows.npz")
    parser.add_argument("--test-npz", default="datasets/processed/cic_windows.npz")
    parser.add_argument("--checkpoint", default="models/checkpoints/tcn_gru_best.pt")
    parser.add_argument("--output-dir", default="results/cross_dataset")
    args = parser.parse_args()

    train_npz = args.train_npz
    test_npz = args.test_npz
    if not Path(test_npz).exists():
        print(f"[!] Missing {test_npz}")
        print("    Download + prepare CIC first:")
        print("      python scripts/download_dataset.py --name cicids2017 --prefer hf --prepare")
        sys.exit(1)
    run_cross_dataset(train_npz, test_npz, args.checkpoint, args.output_dir)


if __name__ == "__main__":
    main()
