"""Webhook / alert notifier for mitigation events."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional


class AlertNotifier:
    """Fire-and-forget JSON webhooks for containment events."""

    def __init__(self, webhook_url: str = "", enabled: bool = False, min_interval_s: float = 5.0):
        self.webhook_url = webhook_url or ""
        self.enabled = bool(enabled and webhook_url)
        self.min_interval_s = float(min_interval_s)
        self._last_sent = 0.0
        self._lock = threading.Lock()
        self.history: List[Dict[str, Any]] = []

    def configure(self, webhook_url: Optional[str] = None, enabled: Optional[bool] = None) -> Dict[str, Any]:
        with self._lock:
            if webhook_url is not None:
                self.webhook_url = webhook_url
            if enabled is not None:
                self.enabled = bool(enabled and self.webhook_url)
            elif webhook_url is not None:
                self.enabled = bool(self.webhook_url)
            return self.status()

    def status(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "webhook_url": self.webhook_url[:80] + ("…" if len(self.webhook_url) > 80 else ""),
            "min_interval_s": self.min_interval_s,
            "deliveries": len(self.history),
            "last": self.history[-1] if self.history else None,
        }

    def notify(self, event: Dict[str, Any]) -> None:
        if not self.enabled or not self.webhook_url:
            return
        now = time.time()
        with self._lock:
            if now - self._last_sent < self.min_interval_s:
                return
            self._last_sent = now
        payload = {
            "source": "sdn-its-resilience-ai",
            "ts": now,
            "event": event,
        }
        threading.Thread(target=self._post, args=(payload,), daemon=True).start()

    def _post(self, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.webhook_url,
            data=body,
            headers={"Content-Type": "application/json", "User-Agent": "sdn-its-alerts/0.2"},
            method="POST",
        )
        record: Dict[str, Any] = {"ts": payload["ts"], "ok": False}
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                record["ok"] = 200 <= getattr(resp, "status", 200) < 300
                record["status"] = getattr(resp, "status", 200)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            record["error"] = str(exc)
        with self._lock:
            self.history.append(record)
            if len(self.history) > 50:
                self.history = self.history[-50:]
