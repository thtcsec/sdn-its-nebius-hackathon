"""Shared utilities: paths, config loading, logging."""

from .paths import PROJECT_ROOT, ensure_dir
from .config import load_config
from .logging_utils import get_logger

__all__ = ["PROJECT_ROOT", "ensure_dir", "load_config", "get_logger"]
