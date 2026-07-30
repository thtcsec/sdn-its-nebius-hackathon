"""YAML configuration loader."""

from pathlib import Path
from typing import Any, Dict

import yaml

from .paths import PROJECT_ROOT


def load_config(name_or_path: str) -> Dict[str, Any]:
    """
    Load a YAML config by filename under configs/ or by absolute/relative path.

    Examples:
        load_config("default")
        load_config("train.yaml")
        load_config("configs/controller.yaml")
    """
    path = Path(name_or_path)
    if not path.suffix:
        path = Path(f"{name_or_path}.yaml")
    if not path.is_absolute() and not path.exists():
        candidate = PROJECT_ROOT / "configs" / path.name
        if candidate.exists():
            path = candidate
        else:
            path = PROJECT_ROOT / path
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
