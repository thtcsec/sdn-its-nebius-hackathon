from collections import deque

import numpy as np
import torch


class StreamingTelemetryBuffer:
    """
    Sliding Window Circular Telemetry Buffer for real-time edge inference.
    Maintains a rolling queue of sequence length L (default L=10) with 10 flow-level feature counters.
    """
    def __init__(self, seq_len: int = 10, num_features: int = 10):
        self.seq_len = seq_len
        self.num_features = num_features
        self.buffer = deque(maxlen=seq_len)

        # Pre-fill buffer with nominal baseline features
        for _ in range(seq_len):
            self.buffer.append(np.zeros(num_features, dtype=np.float32))

    def push(self, feature_vector: list[float]) -> np.ndarray:
        """Pushes a new 10-dimensional flow feature vector into the rolling buffer."""
        if len(feature_vector) != self.num_features:
            raise ValueError(f"Expected feature vector of length {self.num_features}, got {len(feature_vector)}")

        self.buffer.append(np.array(feature_vector, dtype=np.float32))
        return self.get_tensor()

    def get_tensor(self) -> torch.Tensor:
        """Returns the current sliding window buffer formatted as a PyTorch tensor (1, seq_len, num_features)."""
        seq_array = np.array(self.buffer, dtype=np.float32) # shape: (seq_len, num_features)
        tensor = torch.from_numpy(seq_array).unsqueeze(0) # shape: (1, seq_len, num_features)
        return tensor

    def is_full(self) -> bool:
        return len(self.buffer) == self.seq_len

    def reset(self):
        self.buffer.clear()
        for _ in range(self.seq_len):
            self.buffer.append(np.zeros(self.num_features, dtype=np.float32))
