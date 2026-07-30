"""Per-feature reconstruction attribution (lightweight explainability)."""

from __future__ import annotations

import torch

from sdn_its.telemetry.schema import FEATURE_COLUMNS


def feature_attribution(x: torch.Tensor, x_hat: torch.Tensor) -> dict[str, float]:
    """
    Attribute RE contribution per feature: mean squared error over the sequence.

    Args:
        x, x_hat: tensors shaped [B, L, F]
    """
    if x.dim() != 3:
        return {}
    diff = (x - x_hat) ** 2
    # mean over batch + time → [F]
    per_feat = diff.mean(dim=(0, 1)).detach().cpu().tolist()
    names = list(FEATURE_COLUMNS)
    out: dict[str, float] = {}
    for i, val in enumerate(per_feat):
        name = names[i] if i < len(names) else f"f{i}"
        out[name] = round(float(val), 6)
    return out


def top_features(attribution: dict[str, float], k: int = 3) -> list[tuple[str, float]]:
    return sorted(attribution.items(), key=lambda kv: kv[1], reverse=True)[:k]
