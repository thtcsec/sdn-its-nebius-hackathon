"""Load cached empirical evaluation metrics for the ops console."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sdn_its.utils.paths import PROJECT_ROOT

_FALLBACK = {
    "insdn_in_domain": {
        "source": "results/tcn_gru/eval_metrics.json (fallback constants)",
        "n_test": 7500,
        "cls_binary_accuracy": 0.9621,
        "cls_binary_f1": 0.9768,
        "cls_binary_precision": 0.9595,
        "cls_binary_recall": 0.9947,
        "roc_auc": 0.9769,
        "inference_ms": 0.25,
        "idl_ms": 6.45,
        "t_response_ms": 9.95,
    },
    "cic_zero_shot": {
        "source": "results/cross_dataset/adapted_metrics.json → zero_shot_holdout",
        "n_test": 63993,
        "cls_binary_accuracy": 0.7153,
        "cls_binary_f1": 0.6278,
        "roc_auc": 0.7429,
    },
    "cic_adapted": {
        "source": "results/cross_dataset/adapted_metrics.json → adapted_holdout",
        "n_test": 63993,
        "cls_binary_accuracy": 0.9860,
        "cls_binary_f1": 0.9772,
        "roc_auc": 0.9981,
        "delta_f1": 0.3494,
        "delta_acc": 0.2707,
    },
    "notes": [
        "Classifier-head binary metrics (class>0 = anomaly).",
        "RE-threshold path is weaker on real InSDN — report both in papers.",
        "Demo scenario inject can override labels unless Lab mode disables it.",
    ],
}


def _read_json(rel: str) -> dict[str, Any] | None:
    path = PROJECT_ROOT / rel
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_empirical_metrics() -> dict[str, Any]:
    out = {
        "insdn_in_domain": dict(_FALLBACK["insdn_in_domain"]),
        "cic_zero_shot": dict(_FALLBACK["cic_zero_shot"]),
        "cic_adapted": dict(_FALLBACK["cic_adapted"]),
        "notes": list(_FALLBACK["notes"]),
        "files_found": [],
    }

    insdn = _read_json("results/tcn_gru/eval_metrics.json")
    if insdn:
        out["files_found"].append("results/tcn_gru/eval_metrics.json")
        out["insdn_in_domain"] = {
            "source": "results/tcn_gru/eval_metrics.json",
            "n_test": insdn.get("n_test"),
            "cls_binary_accuracy": insdn.get("cls_binary_accuracy"),
            "cls_binary_f1": insdn.get("cls_binary_f1"),
            "cls_binary_precision": insdn.get("cls_binary_precision"),
            "cls_binary_recall": insdn.get("cls_binary_recall"),
            "roc_auc": insdn.get("roc_auc"),
            "inference_ms": insdn.get("inference_ms"),
            "idl_ms": insdn.get("idl_ms"),
            "t_response_ms": insdn.get("t_response_ms"),
            "arch": insdn.get("arch"),
            "checkpoint": insdn.get("checkpoint"),
        }

    adapt = _read_json("results/cross_dataset/adapted_metrics.json")
    if adapt:
        out["files_found"].append("results/cross_dataset/adapted_metrics.json")
        zs = adapt.get("zero_shot_holdout") or {}
        ad = adapt.get("adapted_holdout") or {}
        out["cic_zero_shot"] = {
            "source": "results/cross_dataset/adapted_metrics.json#zero_shot_holdout",
            "n_test": zs.get("n_test"),
            "cls_binary_accuracy": zs.get("cls_binary_accuracy"),
            "cls_binary_f1": zs.get("cls_binary_f1"),
            "roc_auc": zs.get("roc_auc"),
        }
        out["cic_adapted"] = {
            "source": "results/cross_dataset/adapted_metrics.json#adapted_holdout",
            "n_test": ad.get("n_test"),
            "cls_binary_accuracy": ad.get("cls_binary_accuracy"),
            "cls_binary_f1": ad.get("cls_binary_f1"),
            "roc_auc": ad.get("roc_auc"),
            "delta_f1": adapt.get("delta_f1"),
            "delta_acc": adapt.get("delta_acc"),
            "checkpoint_out": adapt.get("checkpoint_out"),
        }

    cross = _read_json("results/cross_dataset/eval_metrics.json")
    if cross and "cic_zero_shot" not in (out.get("files_found") or []):
        out["files_found"].append("results/cross_dataset/eval_metrics.json")

    # Checkpoint presence (not sizes — keep payload light)
    ckpts = {
        "tcn_gru_best": (PROJECT_ROOT / "models/checkpoints/tcn_gru_best.pt").exists(),
        "transformer_best": (PROJECT_ROOT / "models/checkpoints/transformer_best.pt").exists(),
        "tcn_gru_cic_adapted": (PROJECT_ROOT / "models/checkpoints/tcn_gru_cic_adapted.pt").exists(),
    }
    out["checkpoints"] = ckpts
    return out
