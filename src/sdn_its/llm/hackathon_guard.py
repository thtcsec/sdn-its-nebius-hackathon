"""Server-side guards for JunctionTrace / hackathon investigation APIs.

Shared across ALL model-invocation routes. Hosted demos fail closed on bad
config. Daily budget uses SQLite-backed atomic reservation (single-worker).

This is an *application* spending quota — not a Nebius provider hard cap.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Generator

from sdn_its.utils.paths import PROJECT_ROOT

# Weak / placeholder tokens rejected when SDN_HOSTED_DEMO=1
_INSECURE_TOKENS = frozenset(
    {
        "changeme",
        "password",
        "secret",
        "admin",
        "judge",
        "token",
        "test",
        "demo",
        "sdn",
        "hackathon",
        "junctiontrace",
        "jt",
        "1234567890123456",
        # Exact copy-paste values from deploy/judge/.env.example (and cousins)
        "replace-with-32plus-char-random-token",
        "replace-with-a-strong-random-token",
        "your-sdn-api-token-here",
        "changeme-changeme-12",
    }
)

# Substrings that mark documentation / template secrets (case-insensitive)
_INSECURE_TOKEN_FRAGMENTS = (
    "replace-with",
    "replace_with",
    "your-",
    "your_",
    "example",
    "placeholder",
    "changeme",
    "todo",
    "xxx",
    "dummy",
    "notasecret",
    "insert-",
    "paste-",
)


class HostedConfigError(RuntimeError):
    """Unsafe hosted configuration — refuse to accept traffic."""


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


def _truthy(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def hosted_demo_flag() -> bool:
    """Explicit hosted-demo mode (fail-closed startup applies)."""
    return _truthy("SDN_HOSTED_DEMO") or _truthy("JT_HOSTED_DEMO")


def hosted_demo_enforced() -> bool:
    """When true, ignore client overrides of demo safety policy."""
    if hosted_demo_flag():
        return True
    # Token-configured deployments are treated as judge-facing for policy.
    return bool((os.environ.get("SDN_API_TOKEN") or "").strip())


def legacy_model_routes_disabled() -> bool:
    """Disable /run and /investigate only under explicit SDN_HOSTED_DEMO.

    Local research with a lab token keeps legacy routes, but real-mode still
    shares the quota/rate guard. Hosted product path is /multistep only.
    """
    return hosted_demo_flag()


def token_is_secure(token: str | None) -> bool:
    """Return True only for non-placeholder judge tokens.

    Explicitly rejects values copied from .env.example (e.g.
    ``replace-with-32plus-char-random-token``) and other template patterns.
    """
    tok = (token or "").strip()
    if len(tok) < 16:
        return False
    low = tok.lower()
    if low in _INSECURE_TOKENS:
        return False
    if any(frag in low for frag in _INSECURE_TOKEN_FRAGMENTS):
        return False
    # Reject all-same-character / very low-entropy tokens
    if len(set(tok)) < 8:
        return False
    return True


def is_loopback_host(host: str) -> bool:
    h = (host or "").strip().lower()
    return h in {"127.0.0.1", "::1", "localhost"}


def resolve_demo_policy(
    client_demo_mode: bool,
    client_allow_containment: bool,
) -> tuple[bool, bool, list[str]]:
    """Return (demo_mode, allow_containment_in_demo, notes)."""
    notes: list[str] = []
    if hosted_demo_enforced():
        notes.append("server_enforced_demo_policy")
        return True, False, notes
    return bool(client_demo_mode), bool(client_allow_containment), notes


def resolve_request_safety_flags(data: dict[str, Any] | None) -> dict[str, Any]:
    """Server-authoritative safety flags. Client cannot disable on hosted."""
    data = data or {}
    demo_mode, allow_containment, notes = resolve_demo_policy(
        bool(data.get("demo_mode", True)),
        bool(data.get("allow_containment_in_demo", False)),
    )
    apply_gate = bool(data.get("apply_gate", True))
    apply_policy = bool(data.get("apply_policy", False))
    if hosted_demo_enforced():
        apply_gate = True
        apply_policy = False  # never map investigation → PolicyEngine containment on hosted
        notes = list(notes) + ["apply_policy_disabled_hosted", "apply_gate_forced"]
    return {
        "demo_mode": demo_mode,
        "allow_containment_in_demo": allow_containment,
        "apply_gate": apply_gate,
        "apply_policy": apply_policy,
        "server_policy_notes": notes,
    }


def validate_hosted_startup(*, bind_host: str, of_backend: str) -> None:
    """Refuse to start when SDN_HOSTED_DEMO=1 and config is unsafe."""
    if not hosted_demo_flag():
        return
    tok = (os.environ.get("SDN_API_TOKEN") or "").strip()
    if not tok:
        raise HostedConfigError(
            "SDN_HOSTED_DEMO=1 requires SDN_API_TOKEN (missing). Refusing to start."
        )
    if not token_is_secure(tok):
        raise HostedConfigError(
            "SDN_HOSTED_DEMO=1 requires a strong SDN_API_TOKEN "
            "(≥16 chars, not a common placeholder). Refusing to start."
        )
    ofb = (of_backend or os.environ.get("SDN_OF_BACKEND") or "mock").strip().lower()
    if ofb not in {"mock", ""}:
        raise HostedConfigError(
            f"SDN_HOSTED_DEMO=1 requires SDN_OF_BACKEND=mock (got {ofb!r}). Refusing to start."
        )
    # Explicit mock recommended — unset defaults to mock which is OK
    if (os.environ.get("SDN_OF_BACKEND") or "").strip() and ofb != "mock":
        raise HostedConfigError("SDN_HOSTED_DEMO=1 requires explicit mock OpenFlow.")


def client_rate_identity(
    *,
    remote_addr: str | None,
    x_forwarded_for: str | None = None,
    trusted_proxy: bool | None = None,
) -> str:
    """Rate-limit identity. Ignore client-supplied XFF unless trusted-proxy mode."""
    if trusted_proxy is None:
        trusted_proxy = _truthy("JT_TRUSTED_PROXY")
    if trusted_proxy and x_forwarded_for:
        # Left-most hop is the original client when the immediate peer is a trusted proxy.
        first = x_forwarded_for.split(",")[0].strip()
        if first:
            return f"xff:{first}"
    addr = (remote_addr or "").strip() or "unknown"
    return f"ip:{addr}"


@dataclass
class GuardDecision:
    ok: bool
    status: int = 200
    error: str | None = None
    detail: str | None = None
    headers: dict[str, str] | None = None
    reservation_id: str | None = None


@dataclass
class QuotaSnapshot:
    day_utc: str
    reserved_usd: float
    estimated_spent_usd: float
    confirmed_spent_usd: float
    daily_budget_usd: float
    inflight_real: int
    reserve_per_request_usd: float
    note: str = (
        "Application-enforced estimated quota for single-worker hosted demo. "
        "Not a Nebius provider hard spending cap."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "day_utc": self.day_utc,
            "reserved_usd": round(self.reserved_usd, 6),
            "estimated_spent_usd": round(self.estimated_spent_usd, 6),
            "confirmed_spent_usd": round(self.confirmed_spent_usd, 6),
            "committed_usd": round(self.reserved_usd + self.estimated_spent_usd, 6),
            "daily_budget_usd": self.daily_budget_usd,
            "inflight_real": self.inflight_real,
            "reserve_per_request_usd": self.reserve_per_request_usd,
            "note": self.note,
        }


class HackathonInferenceGuard:
    """Shared admit/settle for real-mode Nebius calls (SQLite + process locks)."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._db_path = Path(db_path) if db_path else self._default_db_path()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._reclaim_orphans()

    @staticmethod
    def _default_db_path() -> Path:
        raw = (os.environ.get("JT_QUOTA_DB_PATH") or "").strip()
        if raw:
            return Path(raw)
        return PROJECT_ROOT / "artifacts" / "hackathon" / "quota" / "nebius_daily_quota.sqlite"

    def daily_budget_usd(self) -> float:
        return max(0.0, _env_float("NEBIUS_DAILY_BUDGET_USD", 1.0))

    def reserve_per_request_usd(self) -> float:
        return max(0.001, _env_float("JT_RESERVE_USD_PER_REAL", 0.05))

    def rate_limit_per_minute(self) -> int:
        return max(1, _env_int("JT_RATE_LIMIT_PER_MIN", 8))

    def max_concurrent(self) -> int:
        return max(1, _env_int("JT_MAX_CONCURRENT_REAL", 2))

    def max_model_calls(self) -> int:
        return max(1, _env_int("JT_MAX_MODEL_CALLS", 5))

    def request_timeout_s(self) -> float:
        return max(5.0, _env_float("JT_REAL_TIMEOUT_S", 90.0))

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # DELETE journal avoids lingering WAL handles on Windows test cleanup.
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def close(self) -> None:
        """Release any residual SQLite resources (best-effort)."""
        try:
            with self._connect() as conn:
                conn.execute("PRAGMA optimize")
        except Exception:
            pass

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS daily_quota (
                    day_utc TEXT PRIMARY KEY,
                    reserved_usd REAL NOT NULL DEFAULT 0,
                    estimated_spent_usd REAL NOT NULL DEFAULT 0,
                    confirmed_spent_usd REAL NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS reservations (
                    id TEXT PRIMARY KEY,
                    day_utc TEXT NOT NULL,
                    amount_usd REAL NOT NULL,
                    status TEXT NOT NULL,
                    estimated_usd REAL,
                    confirmed_usd REAL,
                    created_at REAL NOT NULL,
                    settled_at REAL
                );
                CREATE TABLE IF NOT EXISTS rate_hits (
                    client_key TEXT NOT NULL,
                    ts REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_rate_hits_key_ts ON rate_hits(client_key, ts);
                CREATE INDEX IF NOT EXISTS idx_reservations_status ON reservations(status);
                """
            )

    def _today(self) -> str:
        return date.today().isoformat()

    def _ensure_day(self, conn: sqlite3.Connection, day: str) -> None:
        conn.execute(
            "INSERT OR IGNORE INTO daily_quota(day_utc, reserved_usd, estimated_spent_usd, confirmed_spent_usd) "
            "VALUES (?, 0, 0, 0)",
            (day,),
        )

    def _reclaim_orphans(self) -> None:
        """On process start, convert crash-orphaned open reservations into spend.

        An interrupted real-mode call may already have incurred Nebius usage.
        Conservatively charge the full reserved amount into estimated_spent_usd
        (do NOT refund) and clear the reservation so concurrency slots reopen.
        """
        with self._lock:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                rows = conn.execute(
                    "SELECT id, day_utc, amount_usd FROM reservations WHERE status='open'"
                ).fetchall()
                now = time.time()
                for row in rows:
                    amount = float(row["amount_usd"])
                    conn.execute(
                        "UPDATE reservations SET status='settled_crash', estimated_usd=?, "
                        "settled_at=? WHERE id=?",
                        (amount, now, row["id"]),
                    )
                    conn.execute(
                        "UPDATE daily_quota SET reserved_usd = MAX(0, reserved_usd - ?), "
                        "estimated_spent_usd = estimated_spent_usd + ? WHERE day_utc=?",
                        (amount, amount, row["day_utc"]),
                    )
                conn.commit()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            day = self._today()
            with self._connect() as conn:
                self._ensure_day(conn, day)
                row = conn.execute(
                    "SELECT reserved_usd, estimated_spent_usd, confirmed_spent_usd FROM daily_quota WHERE day_utc=?",
                    (day,),
                ).fetchone()
                inflight = conn.execute(
                    "SELECT COUNT(*) AS c FROM reservations WHERE status='open' AND day_utc=?",
                    (day,),
                ).fetchone()["c"]
            snap = QuotaSnapshot(
                day_utc=day,
                reserved_usd=float(row["reserved_usd"] if row else 0),
                estimated_spent_usd=float(row["estimated_spent_usd"] if row else 0),
                confirmed_spent_usd=float(row["confirmed_spent_usd"] if row else 0),
                daily_budget_usd=self.daily_budget_usd(),
                inflight_real=int(inflight),
                reserve_per_request_usd=self.reserve_per_request_usd(),
            )
            out = snap.to_dict()
            out.update(
                {
                    "max_concurrent_real": self.max_concurrent(),
                    "rate_limit_per_min": self.rate_limit_per_minute(),
                    "max_model_calls": self.max_model_calls(),
                    "request_timeout_s": self.request_timeout_s(),
                    "hosted_demo_enforced": hosted_demo_enforced(),
                    "legacy_routes_disabled": legacy_model_routes_disabled(),
                    "db_path": str(self._db_path),
                }
            )
            return out

    def admit_real(self, client_key: str) -> GuardDecision:
        """Atomically reserve budget + concurrency + rate slot before inference."""
        key = (client_key or "unknown").strip() or "unknown"
        reserve = self.reserve_per_request_usd()
        budget = self.daily_budget_usd()
        limit = self.rate_limit_per_minute()
        max_c = self.max_concurrent()
        now = time.time()
        day = self._today()
        rid = uuid.uuid4().hex

        with self._lock:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                self._ensure_day(conn, day)
                # Prune old rate hits
                conn.execute("DELETE FROM rate_hits WHERE ts < ?", (now - 60.0,))
                hits = conn.execute(
                    "SELECT COUNT(*) AS c FROM rate_hits WHERE client_key=? AND ts >= ?",
                    (key, now - 60.0),
                ).fetchone()["c"]
                if hits >= limit:
                    conn.rollback()
                    return GuardDecision(
                        ok=False,
                        status=429,
                        error="rate_limited",
                        detail=f"Rate limit {limit}/min exceeded for this client identity.",
                        headers={"Retry-After": "60"},
                    )
                inflight = conn.execute(
                    "SELECT COUNT(*) AS c FROM reservations WHERE status='open'"
                ).fetchone()["c"]
                if inflight >= max_c:
                    conn.rollback()
                    return GuardDecision(
                        ok=False,
                        status=429,
                        error="concurrency_limit",
                        detail=f"Max concurrent real investigations: {max_c}.",
                        headers={"Retry-After": "5"},
                    )
                row = conn.execute(
                    "SELECT reserved_usd, estimated_spent_usd FROM daily_quota WHERE day_utc=?",
                    (day,),
                ).fetchone()
                committed = float(row["reserved_usd"]) + float(row["estimated_spent_usd"])
                if committed + reserve > budget + 1e-12:
                    conn.rollback()
                    return GuardDecision(
                        ok=False,
                        status=429,
                        error="budget_exhausted",
                        detail=(
                            f"Daily application budget ${budget:.2f} exhausted "
                            f"(committed ${committed:.4f}; need reserve ${reserve:.4f}). "
                            "Not a Nebius provider hard cap."
                        ),
                        headers={"Retry-After": "3600"},
                    )
                conn.execute(
                    "INSERT INTO reservations(id, day_utc, amount_usd, status, created_at) VALUES (?,?,?,?,?)",
                    (rid, day, reserve, "open", now),
                )
                conn.execute(
                    "UPDATE daily_quota SET reserved_usd = reserved_usd + ? WHERE day_utc=?",
                    (reserve, day),
                )
                conn.execute("INSERT INTO rate_hits(client_key, ts) VALUES (?, ?)", (key, now))
                conn.commit()
        return GuardDecision(ok=True, reservation_id=rid)

    def settle(
        self,
        reservation_id: str | None,
        *,
        estimated_usd: float | None = None,
        provider_confirmed_usd: float | None = None,
        failed: bool = False,
    ) -> None:
        """Finalize a reservation. Uncertain/failed usage keeps a conservative charge."""
        if not reservation_id:
            return
        with self._lock:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT * FROM reservations WHERE id=?", (reservation_id,)
                ).fetchone()
                if not row or row["status"] != "open":
                    conn.rollback()
                    return
                reserve = float(row["amount_usd"])
                day = row["day_utc"]
                est = 0.0
                if estimated_usd is not None:
                    try:
                        est = max(0.0, float(estimated_usd))
                    except (TypeError, ValueError):
                        est = 0.0
                conf = None
                if provider_confirmed_usd is not None:
                    try:
                        conf = max(0.0, float(provider_confirmed_usd))
                    except (TypeError, ValueError):
                        conf = None
                # Conservative: charge max(estimated, confirmed, or full reserve on failure/uncertain)
                if failed and est <= 0 and conf is None:
                    charge = reserve  # uncertain billable — keep reservation as spend
                else:
                    charge = max(est, conf or 0.0)
                    if charge <= 0:
                        charge = 0.0
                # Never credit unused reserve back above actual if we had a successful cheap call;
                # unused reserve is released.
                release_unused = max(0.0, reserve - charge)
                conn.execute(
                    "UPDATE reservations SET status='settled', estimated_usd=?, confirmed_usd=?, settled_at=? WHERE id=?",
                    (est if est else None, conf, time.time(), reservation_id),
                )
                conn.execute(
                    "UPDATE daily_quota SET reserved_usd = MAX(0, reserved_usd - ?), "
                    "estimated_spent_usd = estimated_spent_usd + ?, "
                    "confirmed_spent_usd = confirmed_spent_usd + ? WHERE day_utc=?",
                    (reserve, charge, conf or 0.0, day),
                )
                conn.commit()

    # Back-compat wrappers used by older tests / call sites
    def check_real_allowed(self, client_key: str) -> GuardDecision:
        return self.admit_real(client_key)

    def release_slot(self, reservation_id: str | None = None) -> None:
        if reservation_id:
            self.settle(reservation_id, estimated_usd=0.0, failed=False)
            return
        # Legacy no-id release: reclaim one orphan open reservation for this process
        with self._lock:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT id FROM reservations WHERE status='open' ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
                conn.commit()
            if row:
                self.settle(row["id"], estimated_usd=0.0, failed=False)

    def record_spend(self, usd: float | None) -> None:
        """Legacy: charge without reservation (prefer settle)."""
        if usd is None:
            return
        try:
            amount = float(usd)
        except (TypeError, ValueError):
            return
        if amount <= 0:
            return
        with self._lock:
            day = self._today()
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                self._ensure_day(conn, day)
                conn.execute(
                    "UPDATE daily_quota SET estimated_spent_usd = estimated_spent_usd + ? WHERE day_utc=?",
                    (amount, day),
                )
                conn.commit()


_GUARD: HackathonInferenceGuard | None = None
_GUARD_LOCK = threading.Lock()


def get_inference_guard() -> HackathonInferenceGuard:
    global _GUARD
    with _GUARD_LOCK:
        if _GUARD is None:
            _GUARD = HackathonInferenceGuard()
        return _GUARD


def reset_inference_guard_for_tests(db_path: Path | None = None) -> HackathonInferenceGuard:
    """Test helper — replaces the singleton (optionally with a temp DB)."""
    global _GUARD
    with _GUARD_LOCK:
        old = _GUARD
        if old is not None:
            try:
                old.close()
            except Exception:
                pass
        if db_path is None:
            # Unique temp db per reset to avoid cross-test pollution
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
            db_path = (
                PROJECT_ROOT
                / "artifacts"
                / "hackathon"
                / "quota"
                / f"_test_quota_{os.getpid()}_{stamp}.sqlite"
            )
        _GUARD = HackathonInferenceGuard(db_path=db_path)
        return _GUARD


@contextmanager
def real_inference_slot(client_key: str) -> Generator[GuardDecision, None, None]:
    """Admit → yield decision → settle on exit (caller sets spend via settle attrs)."""
    guard = get_inference_guard()
    decision = guard.admit_real(client_key)
    # Attach mutable spend fields for the caller
    decision._estimated_usd = None  # type: ignore[attr-defined]
    decision._confirmed_usd = None  # type: ignore[attr-defined]
    decision._failed = False  # type: ignore[attr-defined]
    try:
        yield decision
    except Exception:
        decision._failed = True  # type: ignore[attr-defined]
        raise
    finally:
        if decision.ok and decision.reservation_id:
            guard.settle(
                decision.reservation_id,
                estimated_usd=getattr(decision, "_estimated_usd", None),
                provider_confirmed_usd=getattr(decision, "_confirmed_usd", None),
                failed=bool(getattr(decision, "_failed", False)),
            )
