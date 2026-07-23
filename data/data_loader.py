"""
data_loader.py - Time-Series Telemetry Feature Extractor & Data Loader

Handles flow-level telemetry feature preprocessing for the TCN-GRU model.
Extracts non-DPI timing and counter features (packet rates, inter-arrival time, packet_in frequency).
Provides synthetic telemetry generation for quick local testing when InSDN or CSE-CIC-IDS2018 datasets are absent.
"""

import os
import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
from typing import Tuple, Dict, Any, Optional

# Telemetry Feature Definitions (10 core features suitable for Edge RSU nodes)
FEATURE_COLUMNS = [
    "flow_duration",         # Duration of flow (seconds)
    "packet_rate",           # Forward Packets per second
    "byte_rate",             # Forward Bytes per second
    "pkt_iat_mean",          # Packet Inter-Arrival Time mean (ms)
    "pkt_iat_std",           # Packet Inter-Arrival Time std (ms)
    "packet_len_mean",       # Average packet payload length
    "packet_in_count",       # Number of packet_in events sent to SDN Controller
    "tcp_flags_syn_count",   # SYN flag frequency
    "flow_active_ratio",     # Ratio of active to idle flow time
    "rsu_channel_occupancy"  # RSU wireless channel load (0.0 to 1.0)
]

# Attack/Fault Category Mapping
LABEL_MAPPING = {
    0: "Normal",
    1: "DDoS_PacketIn_Flood",
    2: "LOFT_LowRate_Attack",
    3: "RSU_Link_Fault",
    4: "RushHour_Burst"
}


def generate_synthetic_telemetry(num_samples: int = 2000, seq_len: int = 10, seed: int = 42) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generates synthetic time-series telemetry data mimicking an SDN-enabled V2X Edge Network.
    
    Args:
        num_samples: Number of sequence samples.
        seq_len: Time-series window length.
        seed: Random seed for reproducibility.
        
    Returns:
        X: numpy array of shape (num_samples, seq_len, num_features)
        y: numpy array of shape (num_samples,) containing class labels.
    """
    np.random.seed(seed)
    num_features = len(FEATURE_COLUMNS)
    
    X_list = []
    y_list = []
    
    for _ in range(num_samples):
        # Sample label with probabilities: 60% Normal, 15% DDoS, 10% LOFT, 5% Fault, 10% RushHour
        label = np.random.choice([0, 1, 2, 3, 4], p=[0.60, 0.15, 0.10, 0.05, 0.10])
        
        # Base normal statistics
        base_stats = {
            "flow_duration": np.random.uniform(1.0, 30.0, seq_len),
            "packet_rate": np.random.normal(50, 10, seq_len),
            "byte_rate": np.random.normal(50000, 10000, seq_len),
            "pkt_iat_mean": np.random.normal(20, 5, seq_len),
            "pkt_iat_std": np.random.normal(5, 2, seq_len),
            "packet_len_mean": np.random.normal(1000, 150, seq_len),
            "packet_in_count": np.random.poisson(2, seq_len),
            "tcp_flags_syn_count": np.random.poisson(1, seq_len),
            "flow_active_ratio": np.random.uniform(0.7, 0.95, seq_len),
            "rsu_channel_occupancy": np.random.uniform(0.2, 0.45, seq_len)
        }
        
        # Inject anomalies according to class label
        if label == 1:  # DDoS PacketIn Flood
            base_stats["packet_rate"] *= np.random.uniform(10, 30, seq_len)
            base_stats["packet_in_count"] += np.random.randint(100, 500, seq_len)
            base_stats["rsu_channel_occupancy"] = np.clip(base_stats["rsu_channel_occupancy"] * 2.2, 0.8, 1.0)
            base_stats["pkt_iat_mean"] = np.random.uniform(0.1, 1.0, seq_len)
            
        elif label == 2:  # LOFT Low-Rate Attack
            base_stats["pkt_iat_mean"] = np.random.uniform(500, 1200, seq_len)
            base_stats["packet_in_count"] += np.random.randint(15, 40, seq_len)
            base_stats["flow_active_ratio"] = np.random.uniform(0.1, 0.3, seq_len)
            
        elif label == 3:  # RSU Link Fault
            base_stats["packet_rate"] *= 0.05
            base_stats["byte_rate"] *= 0.05
            base_stats["rsu_channel_occupancy"] = np.random.uniform(0.0, 0.05, seq_len)
            base_stats["flow_active_ratio"] = np.zeros(seq_len, dtype=np.float32)
            
        elif label == 4:  # RushHour Burst (High volume, low packet_in anomaly)
            base_stats["packet_rate"] *= np.random.uniform(2.5, 4.0, seq_len)
            base_stats["byte_rate"] *= np.random.uniform(2.5, 4.0, seq_len)
            base_stats["rsu_channel_occupancy"] = np.random.uniform(0.65, 0.85, seq_len)
            base_stats["packet_in_count"] = np.random.poisson(3, seq_len)  # Low packet_in (legitimate cached flows)
            
        # Construct feature array for this sample
        sample_features = np.column_stack([base_stats[col] for col in FEATURE_COLUMNS])
        X_list.append(sample_features)
        y_list.append(label)
        
    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int64)
    
    return X, y


class TelemetryDataset(Dataset):
    """PyTorch Dataset for Time-Series Telemetry Windows."""
    
    def __init__(self, X: np.ndarray, y: np.ndarray):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.long)
        
    def __len__(self) -> int:
        return len(self.X)
        
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        return self.X[idx], self.y[idx]


class TelemetryDataLoader:
    """Wrapper to prepare normalized Train, Validation, and Test DataLoaders."""
    
    def __init__(self, seq_len: int = 10, batch_size: int = 64):
        self.seq_len = seq_len
        self.batch_size = batch_size
        self.scaler = StandardScaler()
        
    def get_synthetic_loaders(
        self, num_samples: int = 2000, train_ratio: float = 0.7, val_ratio: float = 0.15
    ) -> Tuple[DataLoader, DataLoader, DataLoader]:
        """Returns normalized (train, val, test) PyTorch DataLoaders using synthetic telemetry."""
        X, y = generate_synthetic_telemetry(num_samples=num_samples, seq_len=self.seq_len)
        
        # Fit scaler on 2D shape: (num_samples * seq_len, num_features)
        N, L, F = X.shape
        X_flat = X.reshape(-1, F)
        X_scaled_flat = self.scaler.fit_transform(X_flat)
        X_scaled = X_scaled_flat.reshape(N, L, F)
        
        # Split datasets
        n_train = int(num_samples * train_ratio)
        n_val = int(num_samples * val_ratio)
        
        X_train, y_train = X_scaled[:n_train], y[:n_train]
        X_val, y_val = X_scaled[n_train:n_train+n_val], y[n_train:n_train+n_val]
        X_test, y_test = X_scaled[n_train+n_val:], y[n_train+n_val:]
        
        train_loader = DataLoader(TelemetryDataset(X_train, y_train), batch_size=self.batch_size, shuffle=True)
        val_loader = DataLoader(TelemetryDataset(X_val, y_val), batch_size=self.batch_size, shuffle=False)
        test_loader = DataLoader(TelemetryDataset(X_test, y_test), batch_size=self.batch_size, shuffle=False)
        
        return train_loader, val_loader, test_loader

    def get_csv_loaders(
        self, csv_path: str, train_ratio: float = 0.7, val_ratio: float = 0.15
    ) -> Tuple[DataLoader, DataLoader, DataLoader]:
        """
        Reads flow telemetry features from a CSV file, applies standard normalization,
        and constructs sliding window sequence tensors for PyTorch model loaders.
        """
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV dataset not found at: {csv_path}")
            
        df = pd.read_csv(csv_path)
        
        # Ensure all core features are present in the CSV, otherwise fill with defaults/zeros
        for col in FEATURE_COLUMNS:
            if col not in df.columns:
                print(f"[!] Warning: Feature column '{col}' not found in CSV. Initializing with default 0.0.")
                df[col] = 0.0
                
        # Retrieve target label column if present, else assume 0 (Normal)
        label_col = "label" if "label" in df.columns else "class"
        if label_col in df.columns:
            if df[label_col].dtype == object:
                # Map string labels to numeric codes
                label_mapping = {
                    "normal": 0, "Normal": 0,
                    "ddos": 1, "DDoS": 1, "DDoS_PacketIn_Flood": 1,
                    "loft": 2, "LOFT": 2, "LOFT_LowRate_Attack": 2,
                    "fault": 3, "Fault": 3, "RSU_Link_Fault": 3,
                    "rushhour": 4, "RushHour": 4, "RushHour_Burst": 4
                }
                y_raw = df[label_col].map(lambda val: label_mapping.get(val, 1)).values
            else:
                y_raw = df[label_col].values
        else:
            y_raw = np.zeros(len(df), dtype=np.int64)
            
        X_raw = df[FEATURE_COLUMNS].values
        
        # Fit-transform features
        X_scaled_all = self.scaler.fit_transform(X_raw)
        
        # Form sliding window time-series sequences of length seq_len
        X_windows = []
        y_windows = []
        
        for i in range(len(df) - self.seq_len + 1):
            window_x = X_scaled_all[i : i + self.seq_len]
            window_y = y_raw[i + self.seq_len - 1]  # label of last step in window
            X_windows.append(window_x)
            y_windows.append(window_y)
            
        X_windows = np.array(X_windows, dtype=np.float32)
        y_windows = np.array(y_windows, dtype=np.int64)
        
        num_samples = len(X_windows)
        if num_samples == 0:
            raise ValueError(f"Insufficient dataset rows ({len(df)}) to form sequence of length {self.seq_len}")
            
        n_train = int(num_samples * train_ratio)
        n_val = int(num_samples * val_ratio)
        
        X_train, y_train = X_windows[:n_train], y_windows[:n_train]
        X_val, y_val = X_windows[n_train:n_train+n_val], y_windows[n_train:n_train+n_val]
        X_test, y_test = X_windows[n_train+n_val:], y_windows[n_train+n_val:]
        
        train_loader = DataLoader(TelemetryDataset(X_train, y_train), batch_size=self.batch_size, shuffle=True)
        val_loader = DataLoader(TelemetryDataset(X_val, y_val), batch_size=self.batch_size, shuffle=False)
        test_loader = DataLoader(TelemetryDataset(X_test, y_test), batch_size=self.batch_size, shuffle=False)
        
        return train_loader, val_loader, test_loader


if __name__ == "__main__":
    loader = TelemetryDataLoader(seq_len=10, batch_size=32)
    train_dl, val_dl, test_dl = loader.get_synthetic_loaders(num_samples=500)
    print(f"[OK] TelemetryDataLoader test passed! Batches in Train DL: {len(train_dl)}")
    for x_b, y_b in train_dl:
        print(f"     Batch X shape: {x_b.shape}, Batch Y shape: {y_b.shape}")
        break
