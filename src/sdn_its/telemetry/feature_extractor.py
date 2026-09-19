"""
feature_extractor.py - Time-Series Telemetry Feature Extractor & Data Loader

Handles flow-level telemetry feature preprocessing for the TCN-GRU model.
Accepts canonical FEATURE_COLUMNS CSVs or raw InSDN/CICFlowMeter CSVs via column_mapper.

Split protocol (rows_before_window_v1)
-------------------------------------
Raw rows are partitioned into mutually exclusive train / val / test segments
*before* sliding-window construction. A gap of (seq_len - 1) rows is left between
partitions so no overlapping window can span two splits. StandardScaler is fit on
training rows (or train windows) only.
"""

from __future__ import annotations

import os
from typing import Any

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, Dataset

from .column_mapper import canonicalize_dataframe
from .schema import FEATURE_COLUMNS

SPLIT_PROTOCOL = "rows_before_window_v1"


def generate_synthetic_telemetry(
    num_samples: int = 2000, seq_len: int = 10, seed: int = 42
) -> tuple[np.ndarray, np.ndarray]:
    """Synthetic time-series telemetry for SDN-enabled V2X edge networks.

    Each sample is an independent window (no temporal overlap across samples),
    so train/val/test splits after generation do not create window leakage.
    """
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


def row_partition_bounds(
    n_rows: int,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    seq_len: int = 10,
) -> dict[str, tuple[int, int]]:
    """Mutually exclusive row ranges with a gap of (seq_len-1) between partitions."""
    if n_rows < seq_len * 3:
        raise ValueError(f"Need enough rows for 3 partitions of seq_len={seq_len}, got {n_rows}")
    gap = max(0, seq_len - 1)
    # Allocate usable mass excluding two gaps
    usable = n_rows - 2 * gap
    if usable < seq_len * 3:
        # Fall back: shrink gaps
        gap = max(0, (n_rows - seq_len * 3) // 2)
        usable = n_rows - 2 * gap
    n_train = int(usable * train_ratio)
    n_val = int(usable * val_ratio)
    n_test = usable - n_train - n_val
    # Ensure each partition can form at least one window
    n_train = max(seq_len, n_train)
    n_val = max(seq_len, n_val)
    n_test = max(seq_len, usable - n_train - n_val)
    if n_train + n_val + n_test > usable:
        n_test = max(seq_len, usable - n_train - n_val)
    train_end = n_train
    val_start = train_end + gap
    val_end = val_start + n_val
    test_start = val_end + gap
    test_end = min(n_rows, test_start + n_test)
    # Clamp if rounding overflow
    if test_end < test_start + seq_len:
        test_end = min(n_rows, test_start + seq_len)
    return {
        "train": (0, train_end),
        "val": (val_start, val_end),
        "test": (test_start, test_end),
        "gap": (gap, gap),
    }


def build_windows_from_rows(
    X_rows: np.ndarray, y_rows: np.ndarray, seq_len: int
) -> tuple[np.ndarray, np.ndarray]:
    """Sliding windows (stride=1) entirely within one row partition."""
    if len(X_rows) < seq_len:
        return (
            np.zeros((0, seq_len, X_rows.shape[1]), dtype=np.float32),
            np.zeros((0,), dtype=np.int64),
        )
    Xw, yw = [], []
    for i in range(len(X_rows) - seq_len + 1):
        Xw.append(X_rows[i : i + seq_len])
        yw.append(y_rows[i + seq_len - 1])
    return np.asarray(Xw, dtype=np.float32), np.asarray(yw, dtype=np.int64)


def gap_aware_window_index_split(
    n_windows: int,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    seq_len: int = 10,
) -> dict[str, slice]:
    """Legacy NPZ mitigation: skip (seq_len-1) windows between contiguous splits.

    Assumes windows were built with stride=1 on a contiguous row sequence so that
    window i and window i+k share rows iff k < seq_len.
    """
    gap = max(0, seq_len - 1)
    usable = n_windows - 2 * gap
    if usable < 3:
        # Degenerate tiny sets — contiguous split without gap
        n_train = max(1, int(n_windows * train_ratio))
        n_val = max(1, int(n_windows * val_ratio))
        return {
            "train": slice(0, n_train),
            "val": slice(n_train, n_train + n_val),
            "test": slice(n_train + n_val, n_windows),
        }
    n_train = max(1, int(usable * train_ratio))
    n_val = max(1, int(usable * val_ratio))
    n_test = max(1, usable - n_train - n_val)
    train_end = n_train
    val_start = train_end + gap
    val_end = val_start + n_val
    test_start = val_end + gap
    test_end = min(n_windows, test_start + n_test)
    return {
        "train": slice(0, train_end),
        "val": slice(val_start, val_end),
        "test": slice(test_start, test_end),
    }


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
        self.last_split_meta: dict[str, Any] = {}

    def _loaders_from_arrays(
        self,
        X_tr: np.ndarray,
        y_tr: np.ndarray,
        X_va: np.ndarray,
        y_va: np.ndarray,
        X_te: np.ndarray,
        y_te: np.ndarray,
    ):
        parts = [
            (X_tr, y_tr, True),
            (X_va, y_va, False),
            (X_te, y_te, False),
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

    def _split_independent_windows(self, X_scaled, y, train_ratio, val_ratio):
        """For non-overlapping independent samples (synthetic). Scaler already fit on train below."""
        n = len(X_scaled)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)
        return self._loaders_from_arrays(
            X_scaled[:n_train],
            y[:n_train],
            X_scaled[n_train : n_train + n_val],
            y[n_train : n_train + n_val],
            X_scaled[n_train + n_val :],
            y[n_train + n_val :],
        )

    def get_synthetic_loaders(
        self, num_samples: int = 2000, train_ratio: float = 0.7, val_ratio: float = 0.15
    ):
        X, y = generate_synthetic_telemetry(num_samples=num_samples, seq_len=self.seq_len)
        n = len(X)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)
        # Fit scaler on train windows only
        f = X.shape[-1]
        self.scaler.fit(X[:n_train].reshape(-1, f))
        Xs = self.scaler.transform(X.reshape(-1, f)).reshape(X.shape).astype(np.float32)
        self.last_split_meta = {
            "protocol": "independent_synthetic_windows",
            "n_train": n_train,
            "n_val": n_val,
            "n_test": n - n_train - n_val,
            "leakage_mitigation": "independent_samples_no_temporal_overlap",
        }
        return self._split_independent_windows(Xs, y, train_ratio, val_ratio)

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
        bounds = row_partition_bounds(len(X_raw), train_ratio, val_ratio, self.seq_len)
        tr_a, tr_b = bounds["train"]
        va_a, va_b = bounds["val"]
        te_a, te_b = bounds["test"]

        # Scaler on training rows only
        self.scaler.fit(X_raw[tr_a:tr_b])
        X_scaled = self.scaler.transform(X_raw)

        X_tr, y_tr = build_windows_from_rows(X_scaled[tr_a:tr_b], y_raw[tr_a:tr_b], self.seq_len)
        X_va, y_va = build_windows_from_rows(X_scaled[va_a:va_b], y_raw[va_a:va_b], self.seq_len)
        X_te, y_te = build_windows_from_rows(X_scaled[te_a:te_b], y_raw[te_a:te_b], self.seq_len)
        self.last_split_meta = {
            "protocol": SPLIT_PROTOCOL,
            "row_bounds": {k: list(v) if k != "gap" else list(v) for k, v in bounds.items()},
            "n_train": int(len(X_tr)),
            "n_val": int(len(X_va)),
            "n_test": int(len(X_te)),
            "gap_rows": int(bounds["gap"][0]),
            "seq_len": self.seq_len,
        }
        print(
            f"[+] Split-before-window ({SPLIT_PROTOCOL}): "
            f"train={len(X_tr)} val={len(X_va)} test={len(X_te)} "
            f"gap_rows={bounds['gap'][0]}"
        )
        return self._loaders_from_arrays(X_tr, y_tr, X_va, y_va, X_te, y_te)

    def get_npz_loaders(
        self,
        npz_path: str,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
        already_scaled: bool = False,
    ):
        """Load windows NPZ.

        Preferred format (rows_before_window_v1): X_train/y_train/... keys.
        Legacy format (X, y only): gap-aware window-index split + train-only scaler
        (mitigates overlap leakage assuming stride-1 contiguous construction).
        """
        if not os.path.exists(npz_path):
            raise FileNotFoundError(f"NPZ dataset not found at: {npz_path}")

        data = np.load(npz_path, allow_pickle=True)
        keys = set(data.keys())

        if {"X_train", "y_train", "X_val", "y_val", "X_test", "y_test"} <= keys:
            X_tr = np.asarray(data["X_train"], dtype=np.float32)
            y_tr = np.asarray(data["y_train"], dtype=np.int64)
            X_va = np.asarray(data["X_val"], dtype=np.float32)
            y_va = np.asarray(data["y_val"], dtype=np.int64)
            X_te = np.asarray(data["X_test"], dtype=np.float32)
            y_te = np.asarray(data["y_test"], dtype=np.int64)
            for arr in (X_tr, X_va, X_te):
                if arr.ndim != 3:
                    raise ValueError(f"Expected 3D window arrays, got {arr.shape}")
            self.seq_len = int(X_tr.shape[1])
            f = X_tr.shape[2]

            def _clean(a: np.ndarray) -> np.ndarray:
                a = np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)
                return np.clip(a, -1e7, 1e7)

            X_tr, X_va, X_te = _clean(X_tr), _clean(X_va), _clean(X_te)
            if not already_scaled:
                self.scaler.fit(X_tr.reshape(-1, f))
                X_tr = self.scaler.transform(X_tr.reshape(-1, f)).reshape(X_tr.shape).astype(np.float32)
                X_va = self.scaler.transform(X_va.reshape(-1, f)).reshape(X_va.shape).astype(np.float32)
                X_te = self.scaler.transform(X_te.reshape(-1, f)).reshape(X_te.shape).astype(np.float32)
            else:
                self.scaler.fit(X_tr.reshape(-1, f))
            proto = str(data["protocol"]) if "protocol" in keys else SPLIT_PROTOCOL
            self.last_split_meta = {
                "protocol": proto,
                "n_train": int(len(X_tr)),
                "n_val": int(len(X_va)),
                "n_test": int(len(X_te)),
                "npz": npz_path,
            }
            print(
                f"[+] NPZ split protocol={proto}: "
                f"train={len(X_tr)} val={len(X_va)} test={len(X_te)} (scaler fit on train)"
            )
            return self._loaders_from_arrays(X_tr, y_tr, X_va, y_va, X_te, y_te)

        if "X" not in data or "y" not in data:
            raise ValueError(f"NPZ must contain X/y or split arrays (got {list(data.keys())})")

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

        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        X = np.clip(X, -1e7, 1e7)
        n, l, f = X.shape
        slices = gap_aware_window_index_split(n, train_ratio, val_ratio, self.seq_len)
        X_tr, y_tr = X[slices["train"]], y[slices["train"]]
        X_va, y_va = X[slices["val"]], y[slices["val"]]
        X_te, y_te = X[slices["test"]], y[slices["test"]]

        if already_scaled:
            Xs_tr, Xs_va, Xs_te = X_tr, X_va, X_te
            self.scaler.fit(X_tr.reshape(-1, f))
        else:
            self.scaler.fit(X_tr.reshape(-1, f))
            Xs_tr = self.scaler.transform(X_tr.reshape(-1, f)).reshape(X_tr.shape).astype(np.float32)
            Xs_va = self.scaler.transform(X_va.reshape(-1, f)).reshape(X_va.shape).astype(np.float32)
            Xs_te = self.scaler.transform(X_te.reshape(-1, f)).reshape(X_te.shape).astype(np.float32)
            print(
                f"[*] Standardized legacy NPZ (train-only scaler) "
                f"z mean={float(Xs_tr.mean()):.3g} std={float(Xs_tr.std()):.3g}"
            )

        self.last_split_meta = {
            "protocol": "legacy_window_then_gap_split",
            "warning": (
                "NPZ was built as overlapping windows before split. "
                "Applied gap=(seq_len-1) between window-index partitions and train-only scaler. "
                "Re-run prepare_data for rows_before_window_v1."
            ),
            "n_train": int(len(Xs_tr)),
            "n_val": int(len(Xs_va)),
            "n_test": int(len(Xs_te)),
            "gap_windows": int(self.seq_len - 1),
            "npz": npz_path,
        }
        print(
            f"[!] Legacy NPZ gap-split: train={len(Xs_tr)} val={len(Xs_va)} test={len(Xs_te)} "
            f"(re-prepare recommended for {SPLIT_PROTOCOL})"
        )
        return self._loaders_from_arrays(Xs_tr, y_tr, Xs_va, y_va, Xs_te, y_te)

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
        tr = np.load(train_npz, allow_pickle=True)
        te = np.load(test_npz, allow_pickle=True)

        def _xy(blob):
            if "X_train" in blob.files and "X_test" in blob.files:
                # Concatenate source splits for adaptation / in-domain pool
                X = np.concatenate(
                    [np.asarray(blob["X_train"]), np.asarray(blob["X_val"]), np.asarray(blob["X_test"])],
                    axis=0,
                )
                y = np.concatenate(
                    [np.asarray(blob["y_train"]), np.asarray(blob["y_val"]), np.asarray(blob["y_test"])],
                    axis=0,
                )
                return X, y
            return np.asarray(blob["X"]), np.asarray(blob["y"])

        Xtr, ytr = _xy(tr)
        Xte, yte = _xy(te)
        Xtr = np.nan_to_num(np.asarray(Xtr, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
        ytr = np.asarray(ytr, dtype=np.int64)
        Xte = np.nan_to_num(np.asarray(Xte, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
        yte = np.asarray(yte, dtype=np.int64)
        Xtr = np.clip(Xtr, -1e7, 1e7)
        Xte = np.clip(Xte, -1e7, 1e7)

        n, l, f = Xtr.shape
        self.seq_len = int(l)
        # Gap-aware split within source domain
        slices = gap_aware_window_index_split(n, train_ratio, val_ratio, self.seq_len)
        Xtr_tr, ytr_tr = Xtr[slices["train"]], ytr[slices["train"]]
        Xtr_va, ytr_va = Xtr[slices["val"]], ytr[slices["val"]]

        Xs_tr = self.scaler.fit_transform(Xtr_tr.reshape(-1, f)).reshape(Xtr_tr.shape).astype(np.float32)
        Xs_va = self.scaler.transform(Xtr_va.reshape(-1, f)).reshape(Xtr_va.shape).astype(np.float32)
        nt, lt, ft = Xte.shape
        if (lt, ft) != (l, f):
            raise ValueError(f"Shape mismatch train {Xtr.shape} vs test {Xte.shape}")
        Xs_te = self.scaler.transform(Xte.reshape(-1, ft)).reshape(nt, lt, ft).astype(np.float32)

        train_ds = TelemetryDataset(Xs_tr, ytr_tr)
        val_ds = TelemetryDataset(Xs_va, ytr_va)
        test_ds = TelemetryDataset(Xs_te, yte)
        self.last_split_meta = {
            "protocol": "cross_dataset_holdout",
            "n_train": len(train_ds),
            "n_val": len(val_ds),
            "n_test": len(test_ds),
            "scaler": "fit_on_source_train_only",
        }
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
