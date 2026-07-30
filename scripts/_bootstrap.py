"""Ensure repo root + src/ are on sys.path so `sdn_its` imports work without install."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"

for p in (_SRC, _ROOT):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)
