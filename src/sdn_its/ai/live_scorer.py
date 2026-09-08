"""Live TCN-GRU scoring with explicit MODEL vs SIMULATED sources."""

from __future__ import annotations

import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
import torch

from sdn_its.ai.attribution import feature_attribution
from sdn_its.ai.infer import load_checkpoint
from sdn_its.telemetry.schema import FEATURE_COLUMNS, LABEL_MAPPING
from sdn_its.utils.paths import PROJECT_ROOT

# Indices in FEATURE_COLUMNS
_I_PKT_RATE = FEATURE_COLUMNS.index("packet_rate")
_I_PKT_IN = FEATURE_COLUMNS.index("packet_in_count")
_I_SYN = FEATURE_COLUMNS.index("tcp_flags_syn_count")
_I_IAT = FEATURE_COLUMNS.index("pkt_iat_mean")
_I_OCC = FEATURE_COLUMNS.index("rsu_channel_occupancy")

SCENARIO_GROUND_TRUTH = {
    "normal": "Normal",
    "ddos": "DDoS_PacketIn_Flood",
    "loft": "LOFT_LowRate_Attack",
    "rush_hour": "RushHour_Burst",
    "link_fault": "RSU_Link_Fault",
}


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
        self._load_error: str | None = None
        self._last: dict[str, Any] = {}
        self._dataset_mode = "sample"
        self._scaler_mean: np.ndarray | None = None
        self._scaler_scale: np.ndarray | None = None
        self._preprocess_mode = "none"
        self._ckpt_meta: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        self._load_error = None
        self._scaler_mean = None
        self._scaler_scale = None
        self._preprocess_mode = "none"
        self._ckpt_meta = {}
        try:
            if not Path(self.checkpoint).is_file():
                raise FileNotFoundError(f"checkpoint missing: {self.checkpoint}")
            model, tau, ckpt = load_checkpoint(self.checkpoint, self._device)
            self._model = model
            self._tau = float(tau)
            self._mu = float(ckpt.get("mu_re", 0.0))
            self._std = float(ckpt.get("std_re", 1.0) or 1.0)
            if "tau_threshold" in ckpt:
                self._tau = float(ckpt["tau_threshold"])
            mean = ckpt.get("scaler_mean")
            scale = ckpt.get("scaler_scale")
            if mean is not None and scale is not None:
                self._scaler_mean = np.asarray(mean, dtype=np.float32).reshape(-1)
                self._scaler_scale = np.asarray(scale, dtype=np.float32).reshape(-1)
                self._preprocess_mode = "fitted_standard_scaler"
            else:
                # Honest: live synthetic windows are not on the training scaler
                self._preprocess_mode = "per_window_zscore_DEMO_MISMATCH"
            self._ckpt_meta = {
                "arch": ckpt.get("arch"),
                "seed": ckpt.get("seed"),
                "epoch": ckpt.get("epoch"),
                "npz_path": ckpt.get("npz_path"),
                "csv_path": ckpt.get("csv_path"),
                "label_mapping": ckpt.get("label_mapping"),
            }
            self._loaded = True
        except Exception as exc:
            self._model = None
            self._loaded = False
            self._load_error = str(exc)
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
            mode = "MODEL" if self._loaded else "DEGRADED"
            return {
                "loaded": self._loaded,
                "mode": mode,
                "checkpoint": self.checkpoint,
                "load_error": self._load_error,
                "tau": round(self._tau, 4),
                "mu_re": round(self._mu, 4),
                "std_re": round(self._std, 4),
                "k_sigma": self.k_sigma,
                "hist_size": len(self._re_hist),
                "dataset_mode": self._dataset_mode,
                "preprocess_mode": self._preprocess_mode,
                "has_fitted_scaler": self._scaler_mean is not None,
                "checkpoint_meta": dict(self._ckpt_meta),
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
        x[0, :, 0] = rng.uniform(1.0, 30.0, 10)
        x[0, :, 1] = rng.normal(50, 10, 10)
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

    def _apply_preprocess(self, x: torch.Tensor) -> tuple[torch.Tensor, str]:
        if self._scaler_mean is not None and self._scaler_scale is not None:
            mean = torch.as_tensor(self._scaler_mean, device=x.device, dtype=x.dtype)
            scale = torch.as_tensor(self._scaler_scale, device=x.device, dtype=x.dtype)
            scale = torch.clamp(scale, min=1e-6)
            # x: (B, L, F)
            return (x - mean) / scale, "fitted_standard_scaler"
        # Explicit demo mismatch — do not pretend this matches training
        x = (x - x.mean(dim=(1, 2), keepdim=True)) / (x.std(dim=(1, 2), keepdim=True) + 1e-6)
        return x, "per_window_zscore_DEMO_MISMATCH"

    def score(
        self,
        window: Any | None = None,
        scenario: str = "normal",
        adapt_tau: bool = True,
        allow_scenario_override: bool = True,
        allow_simulation_fallback: bool | None = None,
    ) -> dict[str, Any]:
        """Score a window.

        ``ground_truth`` always reflects the scenario injector label.
        ``prediction`` / ``predicted_label`` always reflect the model (or null if degraded).
        ``attack_type`` is the policy label: prediction in lab; may equal GT when demo override on.
        """
        with self._lock:
            t0 = time.perf_counter()
            ground_truth = SCENARIO_GROUND_TRUTH.get(scenario, scenario)
            if allow_simulation_fallback is None:
                allow_simulation_fallback = bool(allow_scenario_override)

            # ——— DEGRADED: no silent fake numbers in Lab ———
            if not self._loaded or self._model is None:
                if not allow_simulation_fallback:
                    result = {
                        "mode": "DEGRADED",
                        "source": "none",
                        "simulated": False,
                        "inference_disabled": True,
                        "model_loaded": False,
                        "load_error": self._load_error,
                        "reconstruction_error": None,
                        "is_anomaly": False,
                        "is_anomaly_re": False,
                        "is_anomaly_cls": False,
                        "predicted_class": None,
                        "predicted_label": None,
                        "prediction": None,
                        "ground_truth": ground_truth,
                        "attack_type": None,
                        "correct": None,
                        "scenario_override": False,
                        "threshold_tau": round(self._tau, 4),
                        "mu_re": round(self._mu, 4),
                        "std_re": round(self._std, 4),
                        "k_sigma": self.k_sigma,
                        "latency_ms": round((time.perf_counter() - t0) * 1000.0, 3),
                        "attribution": {},
                        "top_features": [],
                        "scenario": scenario,
                        "dataset_mode": self._dataset_mode,
                        "preprocess_mode": "n/a",
                        "ts": time.time(),
                        "banner": "DEGRADED — checkpoint unavailable; inference disabled",
                    }
                    self._last = result
                    return result

                # Explicit SIMULATION MODE (demo UI only)
                base = {"normal": 12.0, "ddos": 86.0, "loft": 72.0, "rush_hour": 18.0}
                re_score = float(base.get(scenario, 14.0) + np.random.uniform(-2, 2))
                pred_idx = {"normal": 0, "ddos": 1, "loft": 2, "rush_hour": 4}.get(scenario, 0)
                attrib = {
                    n: round(abs(float(np.random.normal(0.1, 0.05))), 4) for n in FEATURE_COLUMNS
                }
                model_label = LABEL_MAPPING.get(pred_idx, "Normal")
                result = {
                    "mode": "SIMULATION",
                    "source": "scenario_simulator",
                    "simulated": True,
                    "inference_disabled": False,
                    "model_loaded": False,
                    "load_error": self._load_error,
                    "reconstruction_error": round(re_score, 4),
                    "is_anomaly": pred_idx > 0,
                    "is_anomaly_re": re_score > self._tau,
                    "is_anomaly_cls": pred_idx > 0,
                    "predicted_class": pred_idx,
                    "predicted_label": model_label,
                    "prediction": model_label,
                    "ground_truth": ground_truth,
                    "attack_type": ground_truth if allow_scenario_override else model_label,
                    "correct": (model_label == ground_truth)
                    or (
                        LABEL_MAPPING.get(pred_idx) == ground_truth
                    ),
                    "scenario_override": bool(allow_scenario_override),
                    "threshold_tau": round(self._tau, 4),
                    "mu_re": round(self._mu, 4),
                    "std_re": round(self._std, 4),
                    "k_sigma": self.k_sigma,
                    "latency_ms": round((time.perf_counter() - t0) * 1000.0, 3),
                    "attribution": attrib,
                    "top_features": sorted(attrib.items(), key=lambda kv: kv[1], reverse=True)[:3],
                    "scenario": scenario,
                    "dataset_mode": self._dataset_mode,
                    "preprocess_mode": "simulated",
                    "ts": time.time(),
                    "banner": "SIMULATION MODE — model output is generated for UI demonstration",
                }
                # In simulation, "correct" is scripted — mark honesty
                result["correct"] = None if allow_scenario_override else (model_label == ground_truth)
                result["eval_note"] = "scripted_simulator_not_model_evidence"
                self._last = result
                return result

            # ——— MODEL path ———
            if window is None:
                x = self._synthetic_window(scenario)
                window_source = "synthetic_generator"
            else:
                arr = np.asarray(window, dtype=np.float32)
                if arr.ndim == 2:
                    arr = arr[None, ...]
                x = torch.from_numpy(arr)
                if x.shape[1] == 10 and x.shape[2] != 10:
                    x = x.transpose(1, 2)
                window_source = "provided_window"
            x = x.to(self._device)
            x, preprocess_mode = self._apply_preprocess(x)
            with torch.no_grad():
                x_hat, logits = self._model(x)
                diff = x - x_hat
                re_score = float(torch.sum(diff ** 2, dim=(1, 2)).item())
                pred_idx = int(torch.argmax(logits, dim=1).item())
                conf = float(torch.softmax(logits, dim=1)[0, pred_idx].item())
            attrib = feature_attribution(x, x_hat)

            if adapt_tau and scenario == "normal":
                self._re_hist.append(re_score)
                self._recompute_tau()

            model_label = LABEL_MAPPING.get(pred_idx, "Normal")
            override_applied = False
            policy_label = model_label
            if allow_scenario_override:
                policy_label = ground_truth
                override_applied = True

            cls_anomaly = bool(pred_idx > 0)
            re_anomaly = bool(re_score > self._tau)
            # Normalize labels for correctness (RushHour_Burst vs class name variants)
            correct = model_label == ground_truth or (
                model_label.replace("_", "") == ground_truth.replace("_", "")
            )

            latency_ms = (time.perf_counter() - t0) * 1000.0
            result = {
                "mode": "MODEL",
                "source": "model",
                "simulated": False,
                "inference_disabled": False,
                "model_loaded": True,
                "load_error": None,
                "reconstruction_error": round(re_score, 4),
                "is_anomaly": cls_anomaly if not allow_scenario_override else re_anomaly,
                "is_anomaly_re": re_anomaly,
                "is_anomaly_cls": cls_anomaly,
                "predicted_class": pred_idx,
                "predicted_label": model_label,
                "prediction": model_label,
                "confidence": round(conf, 4),
                "ground_truth": ground_truth,
                "attack_type": policy_label,
                "correct": correct,
                "scenario_override": override_applied,
                "threshold_tau": round(self._tau, 4),
                "mu_re": round(self._mu, 4),
                "std_re": round(self._std, 4),
                "k_sigma": self.k_sigma,
                "latency_ms": round(latency_ms, 3),
                "attribution": attrib,
                "top_features": sorted(attrib.items(), key=lambda kv: kv[1], reverse=True)[:3],
                "scenario": scenario,
                "dataset_mode": self._dataset_mode,
                "preprocess_mode": preprocess_mode,
                "window_source": window_source,
                "checkpoint": self.checkpoint,
                "ts": time.time(),
                "banner": None
                if preprocess_mode == "fitted_standard_scaler"
                else "WARNING — live preprocess ≠ training StandardScaler (per-window z-score)",
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
