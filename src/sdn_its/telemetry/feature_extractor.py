"""
feature_extractor.py - Time-Series Telemetry Feature Extractor & Data Loader

Handles flow-level telemetry feature preprocessing for the TCN-GRU model.
Accepts canonical FEATURE_COLUMNS CSVs or raw InSDN/CICFlowMeter CSVs via column_mapper.
"""

import os

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, Dataset

from .column_mapper import canonicalize_dataframe
from .schema import FEATURE_COLUMNS


def generate_synthetic_telemetry(
    num_samples: int = 2000, seq_len: int = 10, seed: int = 42
) -> tuple[np.ndarray, np.ndarray]:
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

    def get_npz_loaders(
        self,
        npz_path: str,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
        already_scaled: bool = False,
    ):
        """Load prebuilt windows from prepare_data.py (e.g. InSDN ~50k windows).

        By default windows are re-standardized with StandardScaler (prepare_data
        writes raw-scale features). Pass already_scaled=True only if X is z-scored.
        """
        if not os.path.exists(npz_path):
            raise FileNotFoundError(f"NPZ dataset not found at: {npz_path}")

        data = np.load(npz_path)
        if "X" not in data or "y" not in data:
            raise ValueError(f"NPZ must contain arrays 'X' and 'y' (got {list(data.keys())})")

        X = np.asarray(data["X"], dtype=np.float32)
        y = np.asarray(data["y"], dtype=np.int64)
        if X.ndim != 3:
            raise ValueError(f"Expected X shape (N, seq_len, features), got {X.shape}")
        if X.shape[1] != self.seq_len:
            print(
                f"[!] NPZ seq_len={X.shape[1]} differs from loader seq_len={self.seq_len}; "
                f"using NPZ seq_len"
            )
            self.seq_len = int(X.shape[1])

        # Clip extreme CICFlowMeter / InSDN outliers before z-score
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        X = np.clip(X, -1e7, 1e7)

        n, l, f = X.shape
        if already_scaled:
            Xs = X.astype(np.float32)
            self.scaler.fit(X.reshape(-1, f))
        else:
            Xs = self.scaler.fit_transform(X.reshape(-1, f)).reshape(n, l, f).astype(np.float32)
            print(
                f"[*] Standardized NPZ features "
                f"(raw max={float(np.max(np.abs(X))):.3g} → z mean={float(Xs.mean()):.3g} std={float(Xs.std()):.3g})"
            )

        uniq, counts = np.unique(y, return_counts=True)
        dist = {int(u): int(c) for u, c in zip(uniq, counts, strict=True)}
        print(f"[+] Loaded NPZ windows: N={n} shape={X.shape} label_dist={dist}")
        return self._split_windows(Xs, y, train_ratio, val_ratio)

    def resolve_loaders(
        self,
        npz_path: str | None = None,
        csv_path: str | None = None,
        synthetic_samples: int = 2500,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
    ):
        """Prefer NPZ (full InSDN) → CSV → synthetic fallback."""
        if npz_path and os.path.exists(npz_path):
            print(f"[*] Loading processed windows NPZ: {npz_path}")
            return self.get_npz_loaders(npz_path, train_ratio, val_ratio)
        if csv_path and os.path.exists(csv_path):
            print(f"[*] Loading telemetry CSV: {csv_path}")
            return self.get_csv_loaders(csv_path, train_ratio, val_ratio)
        if npz_path:
            print(f"[!] NPZ not found ({npz_path})")
        if csv_path:
            print(f"[!] CSV not found ({csv_path})")
        print(f"[*] Generating synthetic time-series telemetry (n={synthetic_samples})...")
        return self.get_synthetic_loaders(synthetic_samples, train_ratio, val_ratio)

    def get_cross_dataset_loaders(
        self,
        train_npz: str,
        test_npz: str,
        train_ratio: float = 0.85,
        val_ratio: float = 0.15,
        batch_size: int | None = None,
    ):
        """Train/val from train_npz (scaled in-domain); full test_npz as holdout.

        Scaler is fit on train windows only, then applied to holdout — the correct
        cross-dataset protocol (no test leakage).
        """
        if not os.path.exists(train_npz):
            raise FileNotFoundError(f"Train NPZ not found: {train_npz}")
        if not os.path.exists(test_npz):
            raise FileNotFoundError(f"Test NPZ not found: {test_npz}")

        bs = batch_size or self.batch_size
        tr = np.load(train_npz)
        te = np.load(test_npz)
        Xtr = np.nan_to_num(np.asarray(tr["X"], dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
        ytr = np.asarray(tr["y"], dtype=np.int64)
        Xte = np.nan_to_num(np.asarray(te["X"], dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
        yte = np.asarray(te["y"], dtype=np.int64)
        Xtr = np.clip(Xtr, -1e7, 1e7)
        Xte = np.clip(Xte, -1e7, 1e7)

        n, l, f = Xtr.shape
        self.seq_len = int(l)
        Xs_tr = self.scaler.fit_transform(Xtr.reshape(-1, f)).reshape(n, l, f).astype(np.float32)
        nt, lt, ft = Xte.shape
        if (lt, ft) != (l, f):
            raise ValueError(f"Shape mismatch train {Xtr.shape} vs test {Xte.shape}")
        Xs_te = self.scaler.transform(Xte.reshape(-1, ft)).reshape(nt, lt, ft).astype(np.float32)

        # Use almost-all of train as train, small val; entire foreign set as test
        n_train = int(n * train_ratio)
        n_val = max(1, int(n * val_ratio))
        if n_train + n_val > n:
            n_val = max(1, n - n_train)
        train_ds = TelemetryDataset(Xs_tr[:n_train], ytr[:n_train])
        val_ds = TelemetryDataset(Xs_tr[n_train : n_train + n_val], ytr[n_train : n_train + n_val])
        test_ds = TelemetryDataset(Xs_te, yte)

        print(
            f"[+] Cross-dataset: train={len(train_ds)} val={len(val_ds)} "
            f"holdout_test={len(test_ds)} (scaler fit on train only)"
        )
        return (
            DataLoader(train_ds, batch_size=bs, shuffle=True),
            DataLoader(val_ds, batch_size=bs, shuffle=False),
            DataLoader(test_ds, batch_size=bs, shuffle=False),
        )


if __name__ == "__main__":
    loader = TelemetryDataLoader(seq_len=10, batch_size=32)
    train_dl, _, _ = loader.get_synthetic_loaders(num_samples=500)
    print(f"[OK] batches={len(train_dl)}")
