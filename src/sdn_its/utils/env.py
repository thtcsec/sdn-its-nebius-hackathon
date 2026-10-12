"""Centralized repository-root .env loading (python-dotenv).

Precedence: existing process environment variables always win over `.env`.
The `.env` path is resolved from PROJECT_ROOT, not the process cwd.
Never log or return secret values from this module.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .paths import PROJECT_ROOT

_LOADED = False
_LAST_ENV_PATH: Path | None = None


def env_file_path() -> Path:
    return PROJECT_ROOT / ".env"


def load_repo_env(*, override: bool = False) -> Path | None:
    """Load ``<repo>/.env`` into ``os.environ`` if the file exists.

    Args:
        override: If False (default), do not overwrite variables already set
            in the process environment. If True, `.env` wins (tests only).

    Returns:
        Path to the `.env` file when it exists, else None.
    """
    global _LOADED, _LAST_ENV_PATH
    path = env_file_path()
    _LAST_ENV_PATH = path if path.is_file() else None
    if not path.is_file():
        _LOADED = True
        return None
    try:
        from dotenv import load_dotenv
    except ImportError as exc:  # pragma: no cover - dependency should be installed
        raise RuntimeError(
            "python-dotenv is required to load repository .env — "
            'pip install "python-dotenv>=1.0" or pip install -e .'
        ) from exc
    load_dotenv(dotenv_path=path, override=override)
    _LOADED = True
    return path


def ensure_repo_env() -> Path | None:
    """Idempotent load — safe to call from scripts, clients, and Flask."""
    global _LOADED
    if _LOADED and _LAST_ENV_PATH is not None:
        return _LAST_ENV_PATH
    if _LOADED and _LAST_ENV_PATH is None and not env_file_path().is_file():
        return None
    return load_repo_env(override=False)


def getenv_stripped(name: str, default: str | None = None) -> str | None:
    """Read env after ensuring repo `.env` is loaded. Does not echo values."""
    ensure_repo_env()
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = str(raw).strip()
    return value if value else default


def nebius_config_summary() -> dict[str, Any]:
    """Non-secret Nebius config snapshot for evidence artifacts."""
    ensure_repo_env()
    key = os.environ.get("NEBIUS_API_KEY") or ""
    path = env_file_path()
    return {
        "project_root": str(PROJECT_ROOT),
        "env_file": str(path),
        "env_file_exists": path.is_file(),
        "nebius_api_key_present": bool(key.strip()),
        "nebius_api_key_length": len(key.strip()) if key.strip() else 0,
        "nebius_base_url_set": bool((os.environ.get("NEBIUS_BASE_URL") or "").strip()),
        "nebius_model": (os.environ.get("NEBIUS_MODEL") or "").strip() or None,
        "cwd": str(Path.cwd()),
        "note": "Existing process env vars take precedence over .env (override=False).",
    }
