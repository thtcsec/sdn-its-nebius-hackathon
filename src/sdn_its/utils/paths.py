"""Project path helpers."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def ensure_dir(path) -> Path:
    """Create directory if missing and return Path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
