#!/usr/bin/env python
"""Ablation / architecture sweep → results/ablation_report.md."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import _bootstrap  # noqa: F401
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

from sdn_its.ai.compare import GRUOnlyModel, LSTMModel, VanillaRNNModel
from sdn_its.ai.report import write_markdown_report
from sdn_its.ai.tcn_gru import TCNGRUResilienceModel
from sdn_its.telemetry import LABEL_MAPPING, TelemetryDataLoader
from sdn_its.utils.paths import PROJECT_ROOT


def _quick_train(model: nn.Module, loader, epochs: int = 3, device="cpu") -> None:
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    mse = nn.MSELoss()
    ce = nn.CrossEntropyLoss()
    model.train()
    for _ in range(epochs):
        for bx, by in loader:
            bx, by = bx.to(device), by.to(device)
            opt.zero_grad()
            x_hat, logits = model(bx)
            loss = mse(x_hat, bx) + 0.5 * ce(logits, by)
            loss.backward()
            opt.step()


def _eval(model: nn.Module, loader, device="cpu", tau: float | None = None) -> dict:
    model.eval()
    y_true, y_pred = [], []
    res, lats = [], []
    with torch.no_grad():
        for bx, by in loader:
            bx = bx.to(device)
            t0 = time.perf_counter()
            x_hat, logits = model(bx)
            lats.append((time.perf_counter() - t0) * 1000.0 / max(1, bx.size(0)))
            re = torch.sum((bx - x_hat) ** 2, dim=(1, 2)).cpu().numpy()
            res.extend(re.tolist())
            pred = torch.argmax(logits, dim=1).cpu().numpy()
            y_pred.extend(pred.tolist())
            y_true.extend(by.numpy().tolist())
    y_true_bin = [0 if y == 0 else 1 for y in y_true]
    if tau is None:
        normal_re = [r for r, y in zip(res, y_true, strict=False) if y == 0]
        if normal_re:
            mu, sd = float(np.mean(normal_re)), float(np.std(normal_re) + 1e-6)
            tau = mu + 2.0 * sd
        else:
            tau = float(np.percentile(res, 70))
    y_pred_bin = [1 if r > tau else 0 for r in res]
    p, r, f1, _ = precision_recall_fscore_support(y_true_bin, y_pred_bin, average="binary", zero_division=0)
    return {
        "accuracy_cls": float(accuracy_score(y_true, y_pred)),
        "precision": float(p),
        "recall": float(r),
        "f1": float(f1),
        "tau": float(tau),
        "latency_ms_per_sample": float(np.mean(lats)),
        "params": sum(p.numel() for p in model.parameters() if p.requires_grad),
    }


def run_ablation(epochs: int = 3, samples: int = 800, k_list: list[float] | None = None) -> Path:
    k_list = k_list or [1.0, 2.0, 3.0]
    device = torch.device("cpu")
    loader = TelemetryDataLoader(seq_len=10, batch_size=32)
    train_dl, val_dl, test_dl = loader.get_synthetic_loaders(num_samples=samples)
    n_cls = len(LABEL_MAPPING)

    variants = {
        "RNN": VanillaRNNModel(num_classes=n_cls),
        "LSTM": LSTMModel(num_classes=n_cls),
        "GRU": GRUOnlyModel(num_classes=n_cls),
        "TCN-GRU": TCNGRUResilienceModel(num_features=10, num_classes=n_cls),
    }
    ckpt = PROJECT_ROOT / "models/checkpoints/tcn_gru_best.pt"
    if ckpt.exists():
        state = torch.load(ckpt, map_location=device, weights_only=False)
        try:
            variants["TCN-GRU"].load_state_dict(state["model_state_dict"])
        except Exception:
            pass

    rows = {}
    for name, model in variants.items():
        model.to(device)
        if name != "TCN-GRU" or not ckpt.exists():
            print(f"[*] Quick-train {name} ({epochs} epochs)…")
            _quick_train(model, train_dl, epochs=epochs, device=device)
        rows[name] = _eval(model, test_dl, device=device)
        print(f"  {name}: F1={rows[name]['f1']:.3f} lat={rows[name]['latency_ms_per_sample']:.3f}ms")

    # k-sigma ablation on TCN-GRU RE
    model = variants["TCN-GRU"]
    model.eval()
    all_re, all_y = [], []
    with torch.no_grad():
        for bx, by in test_dl:
            x_hat, _ = model(bx)
            re = torch.sum((bx - x_hat) ** 2, dim=(1, 2)).numpy()
            all_re.extend(re.tolist())
            all_y.extend(by.numpy().tolist())
    normal_re = [r for r, y in zip(all_re, all_y, strict=False) if y == 0]
    mu, sd = float(np.mean(normal_re)), float(np.std(normal_re) + 1e-6)
    k_rows = {}
    for k in k_list:
        tau = mu + k * sd
        y_true_bin = [0 if y == 0 else 1 for y in all_y]
        y_pred_bin = [1 if r > tau else 0 for r in all_re]
        p, r, f1, _ = precision_recall_fscore_support(y_true_bin, y_pred_bin, average="binary", zero_division=0)
        # rush-hour false block proxy: class 4 predicted anomaly
        rush_idx = [i for i, y in enumerate(all_y) if y == 4]
        false_block = sum(1 for i in rush_idx if all_re[i] > tau) / max(1, len(rush_idx))
        k_rows[f"k={k}"] = {"tau": tau, "f1": float(f1), "precision": float(p), "recall": float(r), "rush_false_block_rate": float(false_block)}

    out_dir = PROJECT_ROOT / "results" / "ablation"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"architectures": rows, "k_sigma": k_rows, "samples": samples, "epochs": epochs}
    (out_dir / "ablation.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Flatten for MD table
    flat = {}
    for name, m in rows.items():
        for kk, vv in m.items():
            flat[f"{name}.{kk}"] = vv
    for name, m in k_rows.items():
        for kk, vv in m.items():
            flat[f"tau_{name}.{kk}"] = vv

    path = write_markdown_report(
        flat,
        out_dir / "ablation_report.md",
        title="Ablation: Architectures × k·σ",
        extra_sections={
            "Method": (
                "Baselines quick-trained on synthetic telemetry; TCN-GRU loads checkpoint when present. "
                "Binary anomaly = RE > τ. Rush-hour false-block = fraction of RushHour windows over τ."
            )
        },
    )
    print(f"[+] Wrote {path.relative_to(PROJECT_ROOT)}")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--samples", type=int, default=800)
    args = parser.parse_args()
    run_ablation(epochs=args.epochs, samples=args.samples)


if __name__ == "__main__":
    main()
