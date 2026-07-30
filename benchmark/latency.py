"""Latency benchmark (per-sample inference + IDL / T_response estimate)."""

from __future__ import annotations

import time

import numpy as np
import torch

from sdn_its.ai.tcn_gru import TCNGRUResilienceModel
from sdn_its.telemetry import LABEL_MAPPING


def run(n_iters: int = 50) -> dict:
    model = TCNGRUResilienceModel(num_features=10, num_classes=len(LABEL_MAPPING)).eval()
    x = torch.randn(1, 10, 10)
    times = []
    with torch.no_grad():
        for _ in range(n_iters):
            t0 = time.perf_counter()
            model(x)
            times.append((time.perf_counter() - t0) * 1000.0)
    t_inference = float(np.mean(times))
    t_collect, t_process = 5.0, 1.2
    idl = t_collect + t_process + t_inference
    t_response = idl + 0.5 + 2.0 + 1.0
    return {
        "t_inference_ms": t_inference,
        "idl_ms": idl,
        "t_response_ms": t_response,
    }


if __name__ == "__main__":
    print(run())
