"""Shared metric helpers for evaluation and benchmarks."""

from __future__ import annotations

from typing import Dict

import numpy as np
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, roc_auc_score


def binary_anomaly_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_score=None) -> Dict[str, float]:
    prec, rec, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    out = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(prec),
        "recall": float(rec),
        "f1": float(f1),
    }
    if y_score is not None:
        try:
            out["roc_auc"] = float(roc_auc_score(y_true, y_score))
        except ValueError:
            out["roc_auc"] = float("nan")
    return out
