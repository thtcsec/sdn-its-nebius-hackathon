"""Memory / model footprint helpers."""

from __future__ import annotations

import os
from pathlib import Path

import torch

from sdn_its.ai.tcn_gru import TCNGRUResilienceModel
from sdn_its.telemetry import LABEL_MAPPING


def param_count(model: torch.nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def checkpoint_size_mb(path: str) -> float:
    p = Path(path)
    if not p.exists():
        return 0.0
    return p.stat().st_size / (1024 * 1024)


def run(checkpoint: str = "models/checkpoints/tcn_gru_best.pt") -> dict:
    model = TCNGRUResilienceModel(num_features=10, num_classes=len(LABEL_MAPPING))
    return {
        "parameters": param_count(model),
        "checkpoint_mb": checkpoint_size_mb(checkpoint),
        "checkpoint_exists": os.path.exists(checkpoint),
    }


if __name__ == "__main__":
    print(run())
