r"""
train.py - Training Pipeline for TCN-GRU Resilience Model

Trains the hybrid TCN-GRU Autoencoder + Classifier model on time-series telemetry.
Supports multi-task loss optimization:
L_total = L_MSE(x, \hat{x}) + \alpha * L_CE(y_pred, y_true)

Saves trained weights and threshold parameters to models/checkpoints/.
"""

import argparse
import os
import random
import time

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from sdn_its.ai.tcn_gru import TCNGRUResilienceModel
from sdn_its.ai.temporal_transformer import TemporalTransformerModel
from sdn_its.telemetry import LABEL_MAPPING, TelemetryDataLoader
from sdn_its.telemetry.schema import FEATURE_COLUMNS

DEFAULT_NPZ = "datasets/processed/insdn_windows.npz"
DEFAULT_CSV = "datasets/sample/canonical_flows.csv"


def _set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def _build_model(arch: str, num_features: int, num_classes: int) -> torch.nn.Module:
    arch = (arch or "tcn_gru").lower()
    if arch in {"transformer", "temporal_transformer", "attn"}:
        return TemporalTransformerModel(
            num_features=num_features,
            d_model=64,
            nhead=4,
            num_layers=2,
            num_classes=num_classes,
            dropout=0.1,
        )
    return TCNGRUResilienceModel(
        num_features=num_features,
        tcn_channels=[32, 64],
        gru_hidden_dim=64,
        num_classes=num_classes,
        dropout=0.2,
    )


def train_model(
    epochs: int = 15,
    batch_size: int = 64,
    lr: float = 0.001,
    seq_len: int = 10,
    alpha: float = 1.0,
    k_sigma: float = 2.0,
    save_dir: str = "models/checkpoints",
    csv_path: str = None,
    npz_path: str = None,
    arch: str = "tcn_gru",
    seed: int = 42,
    class_weights=None,
    early_stopping_patience: int = 5,
):
    print("=" * 65)
    print("  MODEL TRAINING PIPELINE - SDN-ITS RESILIENCE AI")
    print("=" * 65)

    _set_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[*] Compute Device: {device} | seed={seed} | arch={arch}")

    loader = TelemetryDataLoader(seq_len=seq_len, batch_size=batch_size)
    train_dl, val_dl, test_dl = loader.resolve_loaders(
        npz_path=npz_path,
        csv_path=csv_path,
        synthetic_samples=2500,
    )
    print(f"[+] Train={len(train_dl.dataset)} Val={len(val_dl.dataset)} Test={len(test_dl.dataset)}")

    num_features = 10
    num_classes = len(LABEL_MAPPING)
    model = _build_model(arch, num_features, num_classes).to(device)

    mse_criterion = nn.MSELoss()
    if class_weights:
        weight = torch.tensor(class_weights, dtype=torch.float32, device=device)
        ce_criterion = nn.CrossEntropyLoss(weight=weight)
    else:
        ce_criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=3
    )

    best_val_loss = float("inf")
    epochs_without_improve = 0
    os.makedirs(save_dir, exist_ok=True)
    ckpt_name = "transformer_best.pt" if "transformer" in arch.lower() or arch.lower() == "attn" else "tcn_gru_best.pt"
    best_model_path = os.path.join(save_dir, ckpt_name)

    start_time = time.time()
    for epoch in range(1, epochs + 1):
        model.train()
        train_mse_sum, train_ce_sum, train_total_sum = 0.0, 0.0, 0.0

        for batch_x, batch_y in train_dl:
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)
            optimizer.zero_grad()
            x_hat, logits = model(batch_x)
            normal_mask = batch_y == 0
            if normal_mask.any():
                l_mse = mse_criterion(x_hat[normal_mask], batch_x[normal_mask])
            else:
                l_mse = torch.tensor(0.0, device=device)
            l_ce = ce_criterion(logits, batch_y)
            l_total = l_mse + alpha * l_ce
            l_total.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            train_mse_sum += l_mse.item() * batch_x.size(0)
            train_ce_sum += l_ce.item() * batch_x.size(0)
            train_total_sum += l_total.item() * batch_x.size(0)

        n_train = max(len(train_dl.dataset), 1)
        epoch_mse = train_mse_sum / n_train
        epoch_ce = train_ce_sum / n_train
        epoch_total = train_total_sum / n_train

        model.eval()
        val_mse_sum, val_ce_sum, val_total_sum = 0.0, 0.0, 0.0
        with torch.no_grad():
            for batch_x, batch_y in val_dl:
                batch_x, batch_y = batch_x.to(device), batch_y.to(device)
                x_hat, logits = model(batch_x)
                normal_mask = batch_y == 0
                if normal_mask.any():
                    l_mse = mse_criterion(x_hat[normal_mask], batch_x[normal_mask])
                else:
                    l_mse = torch.tensor(0.0, device=device)
                l_ce = ce_criterion(logits, batch_y)
                l_total = l_mse + alpha * l_ce
                val_mse_sum += l_mse.item() * batch_x.size(0)
                val_ce_sum += l_ce.item() * batch_x.size(0)
                val_total_sum += l_total.item() * batch_x.size(0)

        n_val = max(len(val_dl.dataset), 1)
        val_mse = val_mse_sum / n_val
        val_ce = val_ce_sum / n_val
        val_total = val_total_sum / n_val
        scheduler.step(val_total)

        print(
            f"Epoch [{epoch:02d}/{epochs:02d}] | Train Loss: {epoch_total:.4f} "
            f"(MSE: {epoch_mse:.4f}, CE: {epoch_ce:.4f}) | "
            f"Val Loss: {val_total:.4f} (MSE: {val_mse:.4f}, CE: {val_ce:.4f})"
        )

        if val_total < best_val_loss:
            best_val_loss = val_total
            epochs_without_improve = 0
            normals = [bx[by == 0] for bx, by in val_dl if (by == 0).any()]
            if normals:
                normal_val_x = torch.cat(normals, dim=0).to(device)
                tau = model.calibrate_threshold(normal_val_x, k=k_sigma)
            else:
                tau = 0.5
            ckpt_payload = {
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_loss": val_total,
                "tau_threshold": tau,
                "mu_re": model.mu_re.item(),
                "std_re": model.std_re.item(),
                "label_mapping": LABEL_MAPPING,
                "feature_columns": list(FEATURE_COLUMNS),
                "csv_path": csv_path,
                "npz_path": npz_path,
                "arch": arch,
                "seed": seed,
                "k_sigma": k_sigma,
                "alpha_ce": alpha,
                "loss": "L = L_MSE(normal only) + alpha * L_CE",
                "split_meta": getattr(loader, "last_split_meta", {}),
            }
            # Persist fitted StandardScaler so live inference matches training
            if getattr(loader, "scaler", None) is not None and hasattr(loader.scaler, "mean_"):
                ckpt_payload["scaler_mean"] = loader.scaler.mean_.astype("float32")
                ckpt_payload["scaler_scale"] = loader.scaler.scale_.astype("float32")
                try:
                    import joblib

                    joblib.dump(loader.scaler, os.path.join(save_dir, "scaler.joblib"))
                except Exception:
                    pass
            torch.save(ckpt_payload, best_model_path)
        else:
            epochs_without_improve += 1
            if early_stopping_patience and epochs_without_improve >= early_stopping_patience:
                print(f"[*] Early stopping at epoch {epoch} (patience={early_stopping_patience})")
                break

    total_time = time.time() - start_time
    print("-" * 65)
    print(f"[+] Training Complete in {total_time:.2f}s!")
    print(f"[+] Best Validation Loss: {best_val_loss:.4f}")
    print(f"[+] Checkpoint saved to: {best_model_path}")
    print("=" * 65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train resilience models for SDN ITS")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--seq_len", type=int, default=10)
    parser.add_argument("--k_sigma", type=float, default=2.0)
    parser.add_argument("--alpha", type=float, default=1.0, help="CE weight in L = MSE + alpha*CE")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--arch",
        type=str,
        default="tcn_gru",
        choices=["tcn_gru", "transformer", "attn"],
        help="Model architecture (tcn_gru default, transformer ablation)",
    )
    parser.add_argument(
        "--npz",
        type=str,
        default=DEFAULT_NPZ,
        help="Processed windows NPZ (preferred; from prepare_data --prepare)",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=DEFAULT_CSV,
        help="Fallback canonical / InSDN CSV if NPZ missing",
    )
    parser.add_argument("--synthetic", action="store_true", help="Force synthetic data")
    args = parser.parse_args()

    train_model(
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        seq_len=args.seq_len,
        alpha=args.alpha,
        k_sigma=args.k_sigma,
        seed=args.seed,
        arch=args.arch,
        npz_path=None if args.synthetic else args.npz,
        csv_path=None if args.synthetic else args.csv,
    )
