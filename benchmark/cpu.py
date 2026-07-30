"""CPU inference cost benchmark."""

from __future__ import annotations

import time

import torch

from sdn_its.ai.tcn_gru import TCNGRUResilienceModel
from sdn_its.telemetry import LABEL_MAPPING


def run(n_iters: int = 100, seq_len: int = 10) -> dict:
    model = TCNGRUResilienceModel(num_features=10, num_classes=len(LABEL_MAPPING))
    model.eval()
    x = torch.randn(1, seq_len, 10)
    # warmup
    with torch.no_grad():
        model(x)
    t0 = time.perf_counter()
    with torch.no_grad():
        for _ in range(n_iters):
            model(x)
    elapsed = time.perf_counter() - t0
    return {
        "iters": n_iters,
        "total_sec": elapsed,
        "sec_per_infer": elapsed / n_iters,
        "infer_per_sec": n_iters / elapsed,
    }


if __name__ == "__main__":
    print(run())
