"""Throughput benchmark (samples/sec)."""

from __future__ import annotations

import time

import torch

from sdn_its.ai.tcn_gru import TCNGRUResilienceModel
from sdn_its.telemetry import LABEL_MAPPING


def run(batch_size: int = 64, n_batches: int = 20) -> dict:
    model = TCNGRUResilienceModel(num_features=10, num_classes=len(LABEL_MAPPING)).eval()
    x = torch.randn(batch_size, 10, 10)
    with torch.no_grad():
        model(x)
    t0 = time.perf_counter()
    with torch.no_grad():
        for _ in range(n_batches):
            model(x)
    elapsed = time.perf_counter() - t0
    total_samples = batch_size * n_batches
    return {
        "samples": total_samples,
        "elapsed_sec": elapsed,
        "samples_per_sec": total_samples / elapsed,
    }


if __name__ == "__main__":
    print(run())
