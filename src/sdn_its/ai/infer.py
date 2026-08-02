"""Inference helpers for live TCN-GRU anomaly scoring."""

from __future__ import annotations

from typing import Any

import torch

from sdn_its.ai.tcn_gru import TCNGRUResilienceModel
from sdn_its.telemetry import LABEL_MAPPING


def load_model(
    checkpoint_path: str = "models/checkpoints/tcn_gru_best.pt",
    device: torch.device | None = None,
) -> tuple[TCNGRUResilienceModel, float]:
    device = device or torch.device("cpu")
    from pathlib import Path

    path = Path(checkpoint_path)
    if not path.is_file():
        raise FileNotFoundError(f"checkpoint not found: {checkpoint_path}")

    ckpt = torch.load(path, map_location=device, weights_only=False)
    if "model_state_dict" not in ckpt:
        raise KeyError(f"checkpoint missing model_state_dict: {checkpoint_path}")

    model = TCNGRUResilienceModel(num_features=10, num_classes=len(LABEL_MAPPING))
    model.load_state_dict(ckpt["model_state_dict"])
    tau = float(ckpt.get("tau_threshold", 0.5))
    model.to(device)
    model.eval()
    return model, tau


def infer(model: TCNGRUResilienceModel, x: torch.Tensor, tau: float) -> dict[str, Any]:
    with torch.no_grad():
        x_hat, logits = model(x)
        diff = x - x_hat
        re_score = float(torch.sum(diff ** 2).item())
        pred_class = int(torch.argmax(logits, dim=1).item())
    return {
        "reconstruction_error": re_score,
        "is_anomaly": re_score > tau,
        "predicted_class": pred_class,
        "threshold_tau": tau,
    }
