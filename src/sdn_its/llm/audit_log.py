"""In-process audit history for hackathon investigation runs (no secrets)."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

_LOCK = threading.Lock()
_HISTORY: deque[dict[str, Any]] = deque(maxlen=100)


def record_audit(entry: dict[str, Any]) -> dict[str, Any]:
    row = {
        "ts": time.time(),
        **entry,
    }
    # Never persist credential-looking fields
    for k in list(row.keys()):
        lk = str(k).lower()
        if "api_key" in lk or lk in {"authorization", "token"}:
            row.pop(k, None)
    with _LOCK:
        _HISTORY.appendleft(row)
    return row


def list_audit(*, limit: int = 40) -> list[dict[str, Any]]:
    with _LOCK:
        return list(_HISTORY)[: max(1, min(limit, 100))]


def clear_audit() -> None:
    with _LOCK:
        _HISTORY.clear()
