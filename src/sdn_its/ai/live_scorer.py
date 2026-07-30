"""Live TCN-GRU scoring with online τ adaptation and feature attribution."""

from __future__ import annotations

import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
import torch

from sdn_its.ai.attribution import feature_attribution
from sdn_its.ai.infer import load_model
from sdn_its.telemetry.schema import FEATURE_COLUMNS, LABEL_MAPPING
from sdn_its.utils.paths import PROJECT_ROOT

# Indices in FEATURE_COLUMNS
_I_PKT_RATE = FEATURE_COLUMNS.index("packet_rate")
_I_PKT_IN = FEATURE_COLUMNS.index("packet_in_count")
_I_SYN = FEATURE_COLUMNS.index("tcp_flags_syn_count")
_I_IAT = FEATURE_COLUMNS.index("pkt_iat_mean")
_I_OCC = FEATURE_COLUMNS.index("rsu_channel_occupancy")


class LiveScorer:
    """Thread-safe live inference + sliding-window τ = μ + kσ."""

    def __init__(
        self,
        checkpoint: str = "models/checkpoints/tcn_gru_best.pt",
        k_sigma: float = 2.0,
        window: int = 64,
    ):
        self.checkpoint = (
            str(PROJECT_ROOT / checkpoint)
            if not Path(checkpoint).is_absolute()
            else checkpoint
        )
        self.k_sigma = float(k_sigma)
        self.window = int(window)
        self._lock = threading.RLock()
        self._re_hist: deque[float] = deque(maxlen=self.window)
        self._model = None
        self._tau = 53.12
        self._mu = 0.0
        self._std = 1.0
        self._device = torch.device("cpu")
        self._loaded = False
        self._last: dict[str, Any] = {}
        self._dataset_mode = "sample"
        self._load()

    def _load(self) -> None:
        try:
            model, tau = load_model(self.checkpoint, self._device)
            self._model = model
            self._tau = float(tau)
            ckpt_path = Path(self.checkpoint)
            if ckpt_path.exists():
                ckpt = torch.load(ckpt_path, map_location=self._device, weights_only=False)
                self._mu = float(ckpt.get("mu_re", 0.0))
                self._std = float(ckpt.get("std_re", 1.0) or 1.0)
                if "tau_threshold" in ckpt:
                    self._tau = float(ckpt["tau_threshold"])
            self._loaded = True
        except Exception as exc:
            self._loaded = False
            self._last = {"error": f"model load failed: {exc}"}

    def reload(self, checkpoint: str | None = None) -> dict[str, Any]:
        with self._lock:
            if checkpoint:
                self.checkpoint = (
                    str(PROJECT_ROOT / checkpoint)
                    if not Path(checkpoint).is_absolute()
                    else checkpoint
                )
            self._load()
            return self.status()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "loaded": self._loaded,
                "checkpoint": self.checkpoint,
                "tau": round(self._tau, 4),
                "mu_re": round(self._mu, 4),
                "std_re": round(self._std, 4),
                "k_sigma": self.k_sigma,
                "hist_size": len(self._re_hist),
                "dataset_mode": self._dataset_mode,
                "last": dict(self._last),
            }

    def set_tau(self, tau: float) -> None:
        with self._lock:
            self._tau = float(tau)

    def set_k_sigma(self, k: float) -> None:
        with self._lock:
            self.k_sigma = float(k)
            self._recompute_tau()

    def set_dataset_mode(self, mode: str) -> None:
        with self._lock:
            self._dataset_mode = str(mode)

    def _recompute_tau(self) -> None:
        if len(self._re_hist) < 8:
            return
        arr = np.asarray(self._re_hist, dtype=np.float64)
        self._mu = float(arr.mean())
        self._std = float(arr.std() + 1e-6)
        self._tau = self._mu + self.k_sigma * self._std

    def _synthetic_window(self, scenario: str = "normal") -> torch.Tensor:
        """Build (1, L=10, F=10) window roughly matching training feature scale."""
        rng = np.random.default_rng()
        x = np.zeros((1, 10, 10), dtype=np.float32)
        x[0, :, 0] = rng.uniform(1.0, 30.0, 10)  # flow_duration
        x[0, :, 1] = rng.normal(50, 10, 10)  # packet_rate
        x[0, :, 2] = rng.normal(50000, 10000, 10)
        x[0, :, 3] = rng.normal(20, 5, 10)
        x[0, :, 4] = rng.normal(5, 2, 10)
        x[0, :, 5] = rng.normal(1000, 150, 10)
        x[0, :, 6] = rng.poisson(2, 10).astype(np.float32)
        x[0, :, 7] = rng.poisson(1, 10).astype(np.float32)
        x[0, :, 8] = rng.uniform(0.7, 0.95, 10)
        x[0, :, 9] = rng.uniform(0.2, 0.45, 10)
        if scenario == "ddos":
            x[0, :, _I_PKT_RATE] *= rng.uniform(10, 30, 10)
            x[0, :, _I_PKT_IN] += rng.integers(100, 500, 10)
            x[0, :, _I_SYN] += rng.integers(20, 80, 10)
        elif scenario == "loft":
            x[0, :, _I_IAT] = rng.uniform(500, 1200, 10)
            x[0, :, _I_PKT_IN] += rng.integers(15, 40, 10)
            x[0, :, 8] = rng.uniform(0.1, 0.3, 10)
        elif scenario == "rush_hour":
            x[0, :, _I_PKT_RATE] *= rng.uniform(2.5, 4.0, 10)
            x[0, :, 2] *= rng.uniform(2.5, 4.0, 10)
            x[0, :, _I_OCC] = rng.uniform(0.65, 0.85, 10)
        return torch.from_numpy(x)

    def score(
        self,
        window: Any | None = None,
        scenario: str = "normal",
        adapt_tau: bool = True,
    ) -> dict[str, Any]:
        with self._lock:
            t0 = time.perf_counter()
            if not self._loaded or self._model is None:
                base = {"normal": 12.0, "ddos": 86.0, "loft": 72.0, "rush_hour": 18.0}
                re_score = float(base.get(scenario, 14.0) + np.random.uniform(-2, 2))
                pred_idx = {"normal": 0, "ddos": 1, "loft": 2, "rush_hour": 4}.get(scenario, 0)
                attrib = {n: round(abs(float(np.random.normal(0.1, 0.05))), 4) for n in FEATURE_COLUMNS}
                x = x_hat = None
            else:
                if window is None:
                    x = self._synthetic_window(scenario)
                else:
                    arr = np.asarray(window, dtype=np.float32)
                    if arr.ndim == 2:
                        arr = arr[None, ...]
                    x = torch.from_numpy(arr)
                    if x.shape[1] == 10 and x.shape[2] != 10:
                        x = x.transpose(1, 2)
                x = x.to(self._device)
                with torch.no_grad():
                    x_hat, logits = self._model(x)
                    diff = x - x_hat
                    re_score = float(torch.sum(diff ** 2, dim=(1, 2)).item())
                    pred_idx = int(torch.argmax(logits, dim=1).item())
                attrib = feature_attribution(x, x_hat)

            if adapt_tau and scenario == "normal":
                self._re_hist.append(re_score)
                self._recompute_tau()

            # Scenario override for demo inject (classifier may not dominate RE)
            attack_type = LABEL_MAPPING.get(pred_idx, "Normal")
            if scenario == "ddos":
                attack_type = "DDoS_PacketIn_Flood"
            elif scenario == "loft":
                attack_type = "LOFT_LowRate_Attack"
            elif scenario == "rush_hour":
                attack_type = "RushHour_Burst"
            elif scenario == "normal":
                attack_type = "Normal"

            latency_ms = (time.perf_counter() - t0) * 1000.0
            result = {
                "reconstruction_error": round(re_score, 4),
                "is_anomaly": bool(re_score > self._tau),
                "predicted_class": pred_idx,
                "predicted_label": LABEL_MAPPING.get(pred_idx, "Unknown"),
                "attack_type": attack_type,
                "threshold_tau": round(self._tau, 4),
                "mu_re": round(self._mu, 4),
                "std_re": round(self._std, 4),
                "k_sigma": self.k_sigma,
                "latency_ms": round(latency_ms, 3),
                "attribution": attrib,
                "top_features": sorted(attrib.items(), key=lambda kv: kv[1], reverse=True)[:3],
                "scenario": scenario,
                "dataset_mode": self._dataset_mode,
                "model_loaded": self._loaded,
                "ts": time.time(),
            }
            self._last = result
            return result


_SCORER: LiveScorer | None = None
_SCORER_LOCK = threading.Lock()


def get_live_scorer() -> LiveScorer:
    global _SCORER
    with _SCORER_LOCK:
        if _SCORER is None:
            _SCORER = LiveScorer()
        return _SCORER
