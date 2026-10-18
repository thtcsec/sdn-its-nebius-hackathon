"""Server-side guards for JunctionTrace / hackathon investigation APIs.

Rate limits, concurrency caps, and daily Nebius spend limits are enforced
before any Token Factory call. Never trust client demo_mode flags on hosted.
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date
from typing import Any


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def hosted_demo_enforced() -> bool:
    """When true, ignore client overrides of demo safety policy."""
    flag = (os.environ.get("SDN_HOSTED_DEMO") or os.environ.get("JT_HOSTED_DEMO") or "").strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return True
    # Token-configured deployments are treated as hosted/judge-facing.
    return bool((os.environ.get("SDN_API_TOKEN") or "").strip())


def resolve_demo_policy(client_demo_mode: bool, client_allow_containment: bool) -> tuple[bool, bool, list[str]]:
    """Return (demo_mode, allow_containment_in_demo, notes)."""
    notes: list[str] = []
    if hosted_demo_enforced():
        notes.append("server_enforced_demo_policy")
        return True, False, notes
    return bool(client_demo_mode), bool(client_allow_containment), notes


@dataclass
class GuardDecision:
    ok: bool
    status: int = 200
    error: str | None = None
    detail: str | None = None
    headers: dict[str, str] | None = None


class HackathonInferenceGuard:
    """Process-local rate / concurrency / budget tracker for real-mode calls."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._day: date = date.today()
        self._spent_usd: float = 0.0
        self._inflight: int = 0
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _roll_day(self) -> None:
        today = date.today()
        if today != self._day:
            self._day = today
            self._spent_usd = 0.0

    def daily_budget_usd(self) -> float:
        return max(0.0, _env_float("NEBIUS_DAILY_BUDGET_USD", 1.0))

    def rate_limit_per_minute(self) -> int:
        return max(1, _env_int("JT_RATE_LIMIT_PER_MIN", 8))

    def max_concurrent(self) -> int:
        return max(1, _env_int("JT_MAX_CONCURRENT_REAL", 2))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            self._roll_day()
            return {
                "day_utc": self._day.isoformat(),
                "spent_usd": round(self._spent_usd, 6),
                "daily_budget_usd": self.daily_budget_usd(),
                "inflight_real": self._inflight,
                "max_concurrent_real": self.max_concurrent(),
                "rate_limit_per_min": self.rate_limit_per_minute(),
                "hosted_demo_enforced": hosted_demo_enforced(),
            }

    def check_real_allowed(self, client_key: str) -> GuardDecision:
        """Call before starting a real Nebius investigation."""
        key = (client_key or "unknown").strip() or "unknown"
        now = time.time()
        with self._lock:
            self._roll_day()
            budget = self.daily_budget_usd()
            if self._spent_usd >= budget - 1e-9:
                return GuardDecision(
                    ok=False,
                    status=429,
                    error="budget_exhausted",
                    detail=f"Daily Nebius budget ${budget:.2f} exhausted (spent ${self._spent_usd:.4f}).",
                    headers={"Retry-After": "3600"},
                )
            if self._inflight >= self.max_concurrent():
                return GuardDecision(
                    ok=False,
                    status=429,
                    error="concurrency_limit",
                    detail=f"Max concurrent real investigations: {self.max_concurrent()}.",
                    headers={"Retry-After": "5"},
                )
            q = self._hits[key]
            while q and now - q[0] > 60.0:
                q.popleft()
            limit = self.rate_limit_per_minute()
            if len(q) >= limit:
                return GuardDecision(
                    ok=False,
                    status=429,
                    error="rate_limited",
                    detail=f"Rate limit {limit}/min exceeded for this client.",
                    headers={"Retry-After": "60"},
                )
            q.append(now)
            self._inflight += 1
            return GuardDecision(ok=True)

    def release_slot(self) -> None:
        with self._lock:
            self._inflight = max(0, self._inflight - 1)

    def record_spend(self, usd: float | None) -> None:
        if usd is None:
            return
        try:
            amount = float(usd)
        except (TypeError, ValueError):
            return
        if amount <= 0:
            return
        with self._lock:
            self._roll_day()
            self._spent_usd += amount


_GUARD: HackathonInferenceGuard | None = None
_GUARD_LOCK = threading.Lock()


def get_inference_guard() -> HackathonInferenceGuard:
    global _GUARD
    with _GUARD_LOCK:
        if _GUARD is None:
            _GUARD = HackathonInferenceGuard()
        return _GUARD


def reset_inference_guard_for_tests() -> HackathonInferenceGuard:
    """Test helper — replaces the singleton."""
    global _GUARD
    with _GUARD_LOCK:
        _GUARD = HackathonInferenceGuard()
        return _GUARD
