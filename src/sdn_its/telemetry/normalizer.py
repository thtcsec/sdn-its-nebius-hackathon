"""Feature normalization helpers for telemetry windows."""

from __future__ import annotations

import numpy as np
from sklearn.preprocessing import StandardScaler


class FeatureNormalizer:
    """Wraps StandardScaler for flow-level telemetry features."""

    def __init__(self):
        self.scaler = StandardScaler()
        self.fitted = False

    def fit(self, x: np.ndarray) -> FeatureNormalizer:
        flat = x.reshape(-1, x.shape[-1]) if x.ndim == 3 else x
        self.scaler.fit(flat)
        self.fitted = True
        return self

    def transform(self, x: np.ndarray) -> np.ndarray:
        if not self.fitted:
            raise RuntimeError("FeatureNormalizer must be fit before transform")
        if x.ndim == 3:
            n, l, f = x.shape
            return self.scaler.transform(x.reshape(-1, f)).reshape(n, l, f)
        return self.scaler.transform(x)

    def fit_transform(self, x: np.ndarray) -> np.ndarray:
        return self.fit(x).transform(x)
