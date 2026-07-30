"""
feature_extractor.py - Time-Series Telemetry Feature Extractor & Data Loader

Handles flow-level telemetry feature preprocessing for the TCN-GRU model.
Accepts canonical FEATURE_COLUMNS CSVs or raw InSDN/CICFlowMeter CSVs via column_mapper.
"""

import os
from typing import Tuple

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler

from .column_mapper import canonicalize_dataframe
from .schema import FEATURE_COLUMNS, LABEL_MAPPING


def generate_synthetic_telemetry(
    num_samples: int = 2000, seq_len: int = 10, seed: int = 42
) -> Tuple[np.ndarray, np.ndarray]:
    """Synthetic time-series telemetry for SDN-enabled V2X edge networks."""
    np.random.seed(seed)
    X_list = []
    y_list = []

    for _ in range(num_samples):
        label = np.random.choice([0, 1, 2, 3, 4], p=[0.60, 0.15, 0.10, 0.05, 0.10])
        base_stats = {
            "flow_duration": np.random.uniform(1.0, 30.0, seq_len),
            "packet_rate": np.random.normal(50, 10, seq_len),
            "byte_rate": np.random.normal(50000, 10000, seq_len),
            "pkt_iat_mean": np.random.normal(20, 5, seq_len),
            "pkt_iat_std": np.random.normal(5, 2, seq_len),
            "packet_len_mean": np.random.normal(1000, 150, seq_len),
            "packet_in_count": np.random.poisson(2, seq_len).astype(float),
            "tcp_flags_syn_count": np.random.poisson(1, seq_len).astype(float),
            "flow_active_ratio": np.random.uniform(0.7, 0.95, seq_len),
            "rsu_channel_occupancy": np.random.uniform(0.2, 0.45, seq_len),
        }
        if label == 1:
            base_stats["packet_rate"] *= np.random.uniform(10, 30, seq_len)
            base_stats["packet_in_count"] += np.random.randint(100, 500, seq_len)
            base_stats["rsu_channel_occupancy"] = np.clip(
                base_stats["rsu_channel_occupancy"] * 2.2, 0.8, 1.0
            )
            base_stats["pkt_iat_mean"] = np.random.uniform(0.1, 1.0, seq_len)
        elif label == 2:
            base_stats["pkt_iat_mean"] = np.random.uniform(500, 1200, seq_len)
            base_stats["packet_in_count"] += np.random.randint(15, 40, seq_len)
            base_stats["flow_active_ratio"] = np.random.uniform(0.1, 0.3, seq_len)
        elif label == 3:
            base_stats["packet_rate"] *= 0.05
            base_stats["byte_rate"] *= 0.05
            base_stats["rsu_channel_occupancy"] = np.random.uniform(0.0, 0.05, seq_len)
            base_stats["flow_active_ratio"] = np.zeros(seq_len, dtype=np.float32)
        elif label == 4:
            base_stats["packet_rate"] *= np.random.uniform(2.5, 4.0, seq_len)
            base_stats["byte_rate"] *= np.random.uniform(2.5, 4.0, seq_len)
            base_stats["rsu_channel_occupancy"] = np.random.uniform(0.65, 0.85, seq_len)
            base_stats["packet_in_count"] = np.random.poisson(3, seq_len).astype(float)

        X_list.append(np.column_stack([base_stats[c] for c in FEATURE_COLUMNS]))
        y_list.append(label)

    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.int64)


class TelemetryDataset(Dataset):
    def __init__(self, X: np.ndarray, y: np.ndarray):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.long)

    def __len__(self) -> int:
        return len(self.X)

    def __getitem__(self, idx: int):
        return self.X[idx], self.y[idx]


class TelemetryDataLoader:
    def __init__(self, seq_len: int = 10, batch_size: int = 64):
        self.seq_len = seq_len
        self.batch_size = batch_size
        self.scaler = StandardScaler()
        self.last_source_map = None

    def _split_windows(self, X_scaled, y, train_ratio, val_ratio):
        n = len(X_scaled)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)
        parts = [
            (X_scaled[:n_train], y[:n_train], True),
            (X_scaled[n_train : n_train + n_val], y[n_train : n_train + n_val], False),
            (X_scaled[n_train + n_val :], y[n_train + n_val :], False),
        ]
        loaders = []
        for Xx, yy, shuffle in parts:
            loaders.append(
                DataLoader(
                    TelemetryDataset(Xx, yy),
                    batch_size=self.batch_size,
                    shuffle=shuffle,
                )
            )
        return tuple(loaders)

    def get_synthetic_loaders(
        self, num_samples: int = 2000, train_ratio: float = 0.7, val_ratio: float = 0.15
    ):
        X, y = generate_synthetic_telemetry(num_samples=num_samples, seq_len=self.seq_len)
        n, l, f = X.shape
        Xs = self.scaler.fit_transform(X.reshape(-1, f)).reshape(n, l, f)
        return self._split_windows(Xs, y, train_ratio, val_ratio)

    def get_csv_loaders(
        self, csv_path: str, train_ratio: float = 0.7, val_ratio: float = 0.15
    ):
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV dataset not found at: {csv_path}")

        raw = pd.read_csv(csv_path, low_memory=False)
        canonical, source_map = canonicalize_dataframe(raw)
        self.last_source_map = source_map
        mapped = sum(1 for k, v in source_map.items() if k != "label" and v is not None)
        print(
            f"[*] Canonicalized CSV: {mapped}/{len(FEATURE_COLUMNS)} features "
            f"resolved from source columns"
        )

        X_raw = canonical[FEATURE_COLUMNS].values.astype(np.float64)
        y_raw = canonical["label"].values.astype(np.int64)
        X_scaled = self.scaler.fit_transform(X_raw)

        if len(canonical) < self.seq_len:
            raise ValueError(
                f"Insufficient dataset rows ({len(canonical)}) for seq_len={self.seq_len}"
            )

        X_windows, y_windows = [], []
        for i in range(len(canonical) - self.seq_len + 1):
            X_windows.append(X_scaled[i : i + self.seq_len])
            y_windows.append(y_raw[i + self.seq_len - 1])

        X_windows = np.array(X_windows, dtype=np.float32)
        y_windows = np.array(y_windows, dtype=np.int64)
        print(f"[+] Built {len(X_windows)} sliding windows (seq_len={self.seq_len})")
        return self._split_windows(X_windows, y_windows, train_ratio, val_ratio)


if __name__ == "__main__":
    loader = TelemetryDataLoader(seq_len=10, batch_size=32)
    train_dl, _, _ = loader.get_synthetic_loaders(num_samples=500)
    print(f"[OK] batches={len(train_dl)}")
