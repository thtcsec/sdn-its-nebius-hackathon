"""Empirical architecture comparison: RNN / LSTM / GRU / TCN-GRU / Temporal Transformer."""

from __future__ import annotations

import argparse
import os
import time

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

from sdn_its.ai.tcn_gru import TCNGRUResilienceModel
from sdn_its.ai.temporal_transformer import TemporalTransformerModel
from sdn_its.telemetry import LABEL_MAPPING, TelemetryDataLoader

DEFAULT_NPZ = "datasets/processed/insdn_windows.npz"
DEFAULT_CSV = "datasets/sample/canonical_flows.csv"


class VanillaRNNModel(nn.Module):
    def __init__(self, input_dim=10, hidden_dim=32, num_classes=5):
        super().__init__()
        self.rnn = nn.RNN(input_dim, hidden_dim, batch_first=True)
        self.fc_recon = nn.Linear(hidden_dim, input_dim)
        self.classifier = nn.Linear(hidden_dim, num_classes)

    def forward(self, x):
        out, _ = self.rnn(x)
        last_out = out[:, -1, :]
        recon = self.fc_recon(out)
        logits = self.classifier(last_out)
        return recon, logits


class LSTMModel(nn.Module):
    def __init__(self, input_dim=10, hidden_dim=32, num_classes=5):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, batch_first=True)
        self.fc_recon = nn.Linear(hidden_dim, input_dim)
        self.classifier = nn.Linear(hidden_dim, num_classes)

    def forward(self, x):
        out, _ = self.lstm(x)
        last_out = out[:, -1, :]
        recon = self.fc_recon(out)
        logits = self.classifier(last_out)
        return recon, logits


class GRUOnlyModel(nn.Module):
    def __init__(self, input_dim=10, hidden_dim=32, num_classes=5):
        super().__init__()
        self.gru = nn.GRU(input_dim, hidden_dim, batch_first=True)
        self.fc_recon = nn.Linear(hidden_dim, input_dim)
        self.classifier = nn.Linear(hidden_dim, num_classes)

    def forward(self, x):
        out, _ = self.gru(x)
        last_out = out[:, -1, :]
        recon = self.fc_recon(out)
        logits = self.classifier(last_out)
        return recon, logits


def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def _quick_train(model, train_dl, device, epochs: int = 3, lr: float = 1e-3):
    """Light fine-tune so baselines are not random-init vs loaded TCN-GRU."""
    model.train()
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    mse = nn.MSELoss()
    ce = nn.CrossEntropyLoss()
    for _ in range(epochs):
        for batch_x, batch_y in train_dl:
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)
            opt.zero_grad()
            x_hat, logits = model(batch_x)
            loss = mse(x_hat, batch_x) + ce(logits, batch_y)
            loss.backward()
            opt.step()
    model.eval()


def benchmark_models(
    npz_path: str | None = DEFAULT_NPZ,
    csv_path: str | None = DEFAULT_CSV,
    train_baselines: bool = True,
    epochs: int = 3,
):
    print("=" * 85)
    print("  EMPIRICAL DEEP LEARNING ARCHITECTURE COMPARISON BENCHMARK")
    print("=" * 85)

    device = torch.device("cpu")
    loader = TelemetryDataLoader(seq_len=10, batch_size=32)
    train_dl, val_dl, test_dl = loader.resolve_loaders(
        npz_path=npz_path,
        csv_path=csv_path,
        synthetic_samples=1000,
    )
    print(
        f"[+] Data: train={len(train_dl.dataset)} val={len(val_dl.dataset)} "
        f"test={len(test_dl.dataset)}"
    )

    n_cls = len(LABEL_MAPPING)
    models: dict[str, nn.Module] = {
        "Vanilla RNN": VanillaRNNModel(input_dim=10, num_classes=n_cls),
        "Standard LSTM": LSTMModel(input_dim=10, num_classes=n_cls),
        "GRU Autoencoder": GRUOnlyModel(input_dim=10, num_classes=n_cls),
        "Temporal Transformer": TemporalTransformerModel(num_features=10, num_classes=n_cls),
        "Proposed TCN-GRU": TCNGRUResilienceModel(num_features=10, num_classes=n_cls),
    }

    ckpt_path = "models/checkpoints/tcn_gru_best.pt"
    ckpt = None
    if os.path.exists(ckpt_path):
        ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
        models["Proposed TCN-GRU"].load_state_dict(ckpt["model_state_dict"])
        print(f"[+] Loaded TCN-GRU checkpoint: {ckpt_path}")

    tf_ckpt = "models/checkpoints/transformer_best.pt"
    tf_loaded = False
    if os.path.exists(tf_ckpt):
        tckpt = torch.load(tf_ckpt, map_location=device, weights_only=False)
        models["Temporal Transformer"].load_state_dict(tckpt["model_state_dict"])
        tf_loaded = True
        print(f"[+] Loaded Transformer checkpoint: {tf_ckpt}")

    if train_baselines:
        print(f"[*] Quick-training untrained baselines ({epochs} epochs)...")
        for name, model in models.items():
            if name == "Proposed TCN-GRU" and ckpt is not None:
                continue
            if name == "Temporal Transformer" and tf_loaded:
                continue
            _quick_train(model, train_dl, device, epochs=epochs)

    results = {}
    for name, model in models.items():
        model.to(device)
        model.eval()

        y_true_bin = []
        y_pred_re = []
        y_pred_cls = []
        latencies = []

        with torch.no_grad():
            normals = []
            for bx, by in val_dl:
                mask = by == 0
                if mask.any():
                    normals.append(bx[mask])
                if sum(t.shape[0] for t in normals) >= 64:
                    break
            if normals:
                nx = torch.cat(normals, dim=0)[:256].to(device)
                x_hat_n, _ = model(nx)
                re_n = torch.sum((nx - x_hat_n) ** 2, dim=(1, 2))
                thresh = float((re_n.mean() + 2.0 * re_n.std(unbiased=False)).item())
            else:
                thresh = 0.5 if name != "Proposed TCN-GRU" else float(
                    (ckpt or {}).get("tau_threshold", 0.5)
                )

            for batch_x, batch_y in test_dl:
                batch_x = batch_x.to(device)

                t0 = time.perf_counter()
                x_hat, logits = model(batch_x)
                t1 = time.perf_counter()

                latencies.append((t1 - t0) * 1000.0 / batch_x.size(0))

                diff = batch_x - x_hat
                re_scores = torch.sum(diff ** 2, dim=(1, 2)).cpu().numpy()
                pred_re = (re_scores > thresh).astype(int)
                pred_cls = (torch.argmax(logits, dim=-1).cpu().numpy() > 0).astype(int)
                true_anom = (batch_y.cpu().numpy() > 0).astype(int)

                y_true_bin.extend(true_anom)
                y_pred_re.extend(pred_re)
                y_pred_cls.extend(pred_cls)

        y_true_bin = np.array(y_true_bin)
        y_pred_cls = np.array(y_pred_cls)

        # Primary metrics: classifier head (matches evaluate.py research path)
        acc = accuracy_score(y_true_bin, y_pred_cls) * 100.0
        prec, rec, f1, _ = precision_recall_fscore_support(
            y_true_bin, y_pred_cls, average="binary", zero_division=0
        )

        results[name] = {
            "params": count_parameters(model),
            "acc": acc,
            "rec": rec * 100.0,
            "prec": prec * 100.0,
            "f1": f1 * 100.0,
            "latency": float(np.mean(latencies)),
            "tau": thresh,
        }

    print(
        f"{'Architecture':<22} | {'Params':<10} | {'Accuracy':<10} | {'Recall':<10} | "
        f"{'Precision':<10} | {'F1-Score':<10} | {'Latency/Pkt':<12}"
    )
    print("-" * 100)
    print("(classifier-head binary: class>0 = anomaly)")
    for name, r in results.items():
        print(
            f"{name:<22} | {r['params']:<10} | {r['acc']:.2f}%{'':<3} | {r['rec']:.2f}%{'':<3} | "
            f"{r['prec']:.2f}%{'':<3} | {r['f1']:.2f}%{'':<3} | {r['latency']:.3f} ms"
        )
    print("=" * 100)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare DL architectures on InSDN windows")
    parser.add_argument("--npz", type=str, default=DEFAULT_NPZ)
    parser.add_argument("--csv", type=str, default=DEFAULT_CSV)
    parser.add_argument("--epochs", type=int, default=3, help="Quick-train epochs for baselines")
    parser.add_argument("--no-train", action="store_true", help="Skip quick-train (eval only)")
    parser.add_argument("--synthetic", action="store_true")
    args = parser.parse_args()
    benchmark_models(
        npz_path=None if args.synthetic else args.npz,
        csv_path=None if args.synthetic else args.csv,
        train_baselines=not args.no_train,
        epochs=args.epochs,
    )
