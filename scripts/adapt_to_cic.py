#!/usr/bin/env python
"""Target-domain adaptation: fine-tune InSDN checkpoint on a CIC slice, eval on holdout.

Protocol (fair vs zero-shot):
  1) Fit scaler on InSDN only
  2) Transform CIC with that scaler
  3) Split CIC → adapt (default 20%) + holdout (80%)
  4) Report zero-shot metrics on the SAME holdout
  5) Fine-tune a few epochs on adapt (low LR) + light CORAL on logits
  6) Report adapted metrics on holdout

Example:
  python scripts/adapt_to_cic.py --epochs 8 --adapt-ratio 0.2
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import _bootstrap  # noqa: F401
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    roc_auc_score,
)
from torch.utils.data import DataLoader

from sdn_its.ai.tcn_gru import TCNGRUResilienceModel
from sdn_its.ai.temporal_transformer import TemporalTransformerModel
from sdn_its.telemetry import LABEL_MAPPING, TelemetryDataLoader, TelemetryDataset
from sdn_its.utils.paths import PROJECT_ROOT, ensure_dir


def _build_model(arch: str, num_classes: int) -> nn.Module:
    if arch in {"transformer", "attn", "temporal_transformer"}:
        return TemporalTransformerModel(num_features=10, num_classes=num_classes)
    return TCNGRUResilienceModel(num_features=10, num_classes=num_classes)


def _load_scaled_cic(train_npz: str, test_npz: str, seq_len: int = 10):
    loader = TelemetryDataLoader(seq_len=seq_len, batch_size=64)
    tr = np.load(train_npz)
    te = np.load(test_npz)
    Xtr = np.clip(
        np.nan_to_num(np.asarray(tr["X"], dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0),
        -1e7,
        1e7,
    )
    Xte = np.clip(
        np.nan_to_num(np.asarray(te["X"], dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0),
        -1e7,
        1e7,
    )
    yte = np.asarray(te["y"], dtype=np.int64)
    n, l, f = Xtr.shape
    loader.scaler.fit(Xtr.reshape(-1, f))
    Xs = loader.scaler.transform(Xte.reshape(-1, f)).reshape(Xte.shape[0], l, f).astype(np.float32)
    # Bound OOD z-scores so reconstruction MSE cannot explode during adapt
    Xs = np.clip(Xs, -8.0, 8.0)
    return Xs, yte


def _split_adapt_holdout(X: np.ndarray, y: np.ndarray, adapt_ratio: float, seed: int):
    rng = np.random.default_rng(seed)
    idx = np.arange(len(X))
    rng.shuffle(idx)
    n_adapt = max(1, int(len(X) * adapt_ratio))
    adapt_idx, hold_idx = idx[:n_adapt], idx[n_adapt:]
    return (X[adapt_idx], y[adapt_idx]), (X[hold_idx], y[hold_idx])


@torch.no_grad()
def _eval_cls(model: nn.Module, dl: DataLoader, device: torch.device) -> dict:
    model.eval()
    y_true, y_pred, probs = [], [], []
    for bx, by in dl:
        bx = bx.to(device)
        _, logits = model(bx)
        p = torch.softmax(logits, dim=-1).cpu().numpy()
        pred = np.argmax(p, axis=-1)
        y_true.extend((by.numpy() > 0).astype(int))
        y_pred.extend((pred > 0).astype(int))
        probs.extend(p)
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    probs = np.array(probs)
    acc = float(accuracy_score(y_true, y_pred))
    prec, rec, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    try:
        roc = float(roc_auc_score(y_true, probs[:, 1:].sum(axis=1)))
    except ValueError:
        roc = float("nan")
    return {
        "cls_binary_accuracy": acc,
        "cls_binary_precision": float(prec),
        "cls_binary_recall": float(rec),
        "cls_binary_f1": float(f1),
        "roc_auc": roc if roc == roc else None,
        "n_test": int(len(y_true)),
    }


def _coral_logits(source_logits: torch.Tensor, target_logits: torch.Tensor) -> torch.Tensor:
    """CORAL on class logits (B, C) — numerically stable domain alignment."""
    s = (source_logits - source_logits.mean(dim=0, keepdim=True)) / (
        source_logits.std(dim=0, keepdim=True) + 1e-5
    )
    t = (target_logits - target_logits.mean(dim=0, keepdim=True)) / (
        target_logits.std(dim=0, keepdim=True) + 1e-5
    )
    ns, d = s.size()
    nt = t.size(0)
    cs = (s.t() @ s) / max(ns - 1, 1)
    ct = (t.t() @ t) / max(nt - 1, 1)
    return torch.mean((cs - ct) ** 2) / float(max(d * d, 1))


def adapt(
    source_npz: str,
    target_npz: str,
    checkpoint: str,
    epochs: int = 8,
    adapt_ratio: float = 0.2,
    batch_size: int = 128,
    lr: float = 3e-4,
    alpha: float = 1.0,
    coral_weight: float = 0.5,
    mse_weight: float = 0.0,
    seed: int = 42,
    output_dir: str = "results/cross_dataset",
    save_path: str = "models/checkpoints/tcn_gru_cic_adapted.pt",
):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("=" * 70)
    print("  CIC TARGET ADAPTATION (CE fine-tune + CORAL on logits)")
    print("=" * 70)
    print(
        f"[*] device={device} epochs={epochs} adapt_ratio={adapt_ratio} "
        f"coral={coral_weight} mse_w={mse_weight}"
    )

    torch.manual_seed(seed)
    np.random.seed(seed)

    Xs_cic, y_cic = _load_scaled_cic(source_npz, target_npz)
    (Xa, ya), (Xh, yh) = _split_adapt_holdout(Xs_cic, y_cic, adapt_ratio, seed)
    print(f"[+] CIC adapt={len(Xa)} holdout={len(Xh)} label_adapt={dict(zip(*np.unique(ya, return_counts=True), strict=True))}")

    src_loader = TelemetryDataLoader(seq_len=10, batch_size=batch_size)
    src_train_dl, _, _ = src_loader.get_npz_loaders(source_npz, train_ratio=0.9, val_ratio=0.1)

    hold_dl = DataLoader(TelemetryDataset(Xh, yh), batch_size=batch_size, shuffle=False)
    adapt_dl = DataLoader(TelemetryDataset(Xa, ya), batch_size=batch_size, shuffle=True)

    ckpt = torch.load(checkpoint, map_location=device, weights_only=False)
    arch = ckpt.get("arch", "tcn_gru")
    model = _build_model(arch, len(LABEL_MAPPING)).to(device)
    model.load_state_dict(ckpt["model_state_dict"])

    zero = _eval_cls(model, hold_dl, device)
    print(
        f"[zero-shot holdout] acc={zero['cls_binary_accuracy']*100:.2f}% "
        f"f1={zero['cls_binary_f1']*100:.2f}% roc={zero['roc_auc']}"
    )

    mse = nn.MSELoss()
    ce = nn.CrossEntropyLoss()
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    src_iter = iter(src_train_dl)

    t0 = time.time()
    for ep in range(1, epochs + 1):
        model.train()
        total = 0.0
        n = 0
        for bx, by in adapt_dl:
            bx, by = bx.to(device), by.to(device)
            try:
                sx, _sy = next(src_iter)
            except StopIteration:
                src_iter = iter(src_train_dl)
                sx, _sy = next(src_iter)
            sx = sx.to(device)

            opt.zero_grad()
            x_hat, logits = model(bx)
            _sx_hat, s_logits = model(sx)
            normal = by == 0
            l_mse = (
                mse(x_hat[normal], bx[normal]) if (mse_weight > 0 and normal.any()) else torch.tensor(0.0, device=device)
            )
            l_ce = ce(logits, by)
            l_coral = (
                _coral_logits(s_logits, logits)
                if coral_weight > 0
                else torch.tensor(0.0, device=device)
            )
            loss = mse_weight * l_mse + alpha * l_ce + coral_weight * l_coral
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            total += float(loss.item()) * bx.size(0)
            n += bx.size(0)
        print(f"Epoch [{ep:02d}/{epochs:02d}] adapt_loss={total / max(n, 1):.4f}")

    adapted = _eval_cls(model, hold_dl, device)
    print(
        f"[adapted holdout]  acc={adapted['cls_binary_accuracy']*100:.2f}% "
        f"f1={adapted['cls_binary_f1']*100:.2f}% "
        f"prec={adapted['cls_binary_precision']*100:.2f}% "
        f"rec={adapted['cls_binary_recall']*100:.2f}% roc={adapted['roc_auc']}"
    )

    model.eval()
    normals = []
    with torch.no_grad():
        for bx, by in adapt_dl:
            m = by == 0
            if m.any():
                normals.append(bx[m])
            if sum(t.shape[0] for t in normals) >= 256:
                break
    tau = 0.5
    if normals:
        nx = torch.cat(normals, dim=0)[:512].to(device)
        tau = float(model.calibrate_threshold(nx, k=2.0))

    out_ckpt = PROJECT_ROOT / save_path
    out_ckpt.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "arch": arch,
            "tau_threshold": tau,
            "source_npz": source_npz,
            "target_npz": target_npz,
            "adapt_ratio": adapt_ratio,
            "epochs": epochs,
            "coral_weight": coral_weight,
            "mse_weight": mse_weight,
            "seed": seed,
            "label_mapping": LABEL_MAPPING,
        },
        out_ckpt,
    )

    out = ensure_dir(PROJECT_ROOT / output_dir)
    report = {
        "protocol": "insdn_pretrain_cic_adapt_holdout",
        "device": str(device),
        "checkpoint_in": checkpoint,
        "checkpoint_out": str(out_ckpt.relative_to(PROJECT_ROOT)),
        "adapt_ratio": adapt_ratio,
        "n_adapt": int(len(Xa)),
        "n_holdout": int(len(Xh)),
        "epochs": epochs,
        "lr": lr,
        "coral_weight": coral_weight,
        "mse_weight": mse_weight,
        "seconds": round(time.time() - t0, 2),
        "zero_shot_holdout": zero,
        "adapted_holdout": adapted,
        "delta_f1": adapted["cls_binary_f1"] - zero["cls_binary_f1"],
        "delta_acc": adapted["cls_binary_accuracy"] - zero["cls_binary_accuracy"],
        "delta_roc": (adapted["roc_auc"] or 0) - (zero["roc_auc"] or 0),
    }
    path = out / "adapted_metrics.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("-" * 70)
    print(
        f"[+] ΔF1={report['delta_f1']*100:+.2f}pp  "
        f"ΔAcc={report['delta_acc']*100:+.2f}pp  "
        f"ΔROC={report['delta_roc']:+.3f}"
    )
    print(f"[+] Saved {out_ckpt}")
    print(f"[+] Wrote {path}")
    print("=" * 70)
    return report


def main():
    p = argparse.ArgumentParser(description="Fine-tune InSDN model on CIC adapt split")
    p.add_argument("--source-npz", default="datasets/processed/insdn_windows.npz")
    p.add_argument("--target-npz", default="datasets/processed/cic_windows.npz")
    p.add_argument("--checkpoint", default="models/checkpoints/tcn_gru_best.pt")
    p.add_argument("--epochs", type=int, default=8)
    p.add_argument("--adapt-ratio", type=float, default=0.2)
    p.add_argument("--batch-size", type=int, default=128)
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--coral-weight", type=float, default=0.5)
    p.add_argument("--mse-weight", type=float, default=0.0, help="0 recommended for OOD CIC adapt")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output-dir", default="results/cross_dataset")
    p.add_argument("--save", default="models/checkpoints/tcn_gru_cic_adapted.pt")
    args = p.parse_args()

    if not Path(args.target_npz).exists():
        raise SystemExit(
            f"Missing {args.target_npz}. Run: "
            "python scripts/download_dataset.py --name cicids2017 --prefer hf --prepare"
        )
    adapt(
        source_npz=args.source_npz,
        target_npz=args.target_npz,
        checkpoint=args.checkpoint,
        epochs=args.epochs,
        adapt_ratio=args.adapt_ratio,
        batch_size=args.batch_size,
        lr=args.lr,
        coral_weight=args.coral_weight,
        mse_weight=args.mse_weight,
        seed=args.seed,
        output_dir=args.output_dir,
        save_path=args.save,
    )


if __name__ == "__main__":
    main()
