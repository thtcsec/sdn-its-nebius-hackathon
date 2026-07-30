"""Inference latency CDF over a loaded (or fresh) TCN-GRU checkpoint."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

from sdn_its.ai.infer import load_model
from sdn_its.utils.paths import PROJECT_ROOT


def run(n_iters: int = 200, warmup: int = 20, checkpoint: str = "models/checkpoints/tcn_gru_best.pt") -> dict[str, Any]:
    ckpt = checkpoint if Path(checkpoint).is_absolute() else str(PROJECT_ROOT / checkpoint)
    model, tau = load_model(ckpt)
    model.eval()
    x = torch.randn(1, 10, 10)

    for _ in range(warmup):
        with torch.no_grad():
            model(x)

    samples: list[float] = []
    with torch.no_grad():
        for _ in range(n_iters):
            t0 = time.perf_counter()
            model(x)
            samples.append((time.perf_counter() - t0) * 1000.0)

    arr = np.sort(np.asarray(samples))
    return {
        "n": n_iters,
        "tau": tau,
        "mean_ms": float(arr.mean()),
        "std_ms": float(arr.std()),
        "p50_ms": float(np.percentile(arr, 50)),
        "p90_ms": float(np.percentile(arr, 90)),
        "p95_ms": float(np.percentile(arr, 95)),
        "p99_ms": float(np.percentile(arr, 99)),
        "samples_ms": arr.tolist(),
    }


if __name__ == "__main__":
    import json

    print(json.dumps({k: v for k, v in run().items() if k != "samples_ms"}, indent=2))
