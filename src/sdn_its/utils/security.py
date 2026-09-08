"""Lab-console security helpers (bind defaults, webhook SSRF guard, API token)."""

from __future__ import annotations

import ipaddress
import os
import socket
from typing import Any
from urllib.parse import urlparse

# Mutating REST paths that can install rules / change lab settings.
MUTATING_API_PREFIXES: tuple[str, ...] = (
    "/api/v1/anomaly_alert",
    "/api/v1/settings",
    "/api/v1/infer",
    "/api/v1/replay",
    "/api/v1/camera",
    "/api/v1/mitigation",
    "/api/v1/flow",
    "/api/v1/rollback",
    "/api/v1/webhook",
)


def resolve_bind_host(explicit: str | None = None) -> str:
    """Default to loopback; allow LAN bind only via env or explicit config."""
    if explicit:
        return explicit.strip()
    env = (os.environ.get("SDN_BIND_HOST") or os.environ.get("SDN_HOST") or "").strip()
    if env:
        return env
    if (os.environ.get("SDN_BIND_LAN") or "").strip().lower() in {"1", "true", "yes", "on"}:
        return "0.0.0.0"
    return "127.0.0.1"


def is_loopback_bind(host: str) -> bool:
    h = (host or "").strip().lower()
    return h in {"127.0.0.1", "::1", "localhost"}


def api_token() -> str | None:
    tok = (os.environ.get("SDN_API_TOKEN") or "").strip()
    return tok or None


def require_api_token_for_lan(host: str) -> bool:
    """When binding beyond loopback, prefer requiring SDN_API_TOKEN (warn if missing)."""
    return not is_loopback_bind(host)


def extract_request_token(headers: Any) -> str | None:
    auth = ""
    if headers is not None:
        auth = str(headers.get("Authorization") or headers.get("authorization") or "")
        x = str(headers.get("X-API-Token") or headers.get("x-api-token") or "")
    else:
        x = ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return (x.strip() or None)


def token_ok(provided: str | None, expected: str | None) -> bool:
    if not expected:
        return True
    if not provided:
        return False
    # Constant-time-ish compare for short lab tokens
    if len(provided) != len(expected):
        return False
    acc = 0
    for a, b in zip(provided, expected, strict=True):
        acc |= ord(a) ^ ord(b)
    return acc == 0


def is_mutating_path(path: str, method: str) -> bool:
    m = (method or "GET").upper()
    if m in {"GET", "HEAD", "OPTIONS"}:
        return False
    p = path or ""
    return any(p == pref or p.startswith(pref.rstrip("/") + "/") or p.startswith(pref) for pref in MUTATING_API_PREFIXES)


def _host_is_safe_webhook_target(hostname: str) -> bool:
    host = (hostname or "").strip().lower().rstrip(".")
    if not host:
        return False
    if host in {"localhost"}:
        return True
    # Block obvious cloud metadata
    if host in {"metadata.google.internal", "metadata", "instance-data"}:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if ip.is_loopback:
            continue
        # Allow RFC1918 / link-local only when SDN_WEBHOOK_ALLOW_PRIVATE=1
        allow_priv = (os.environ.get("SDN_WEBHOOK_ALLOW_PRIVATE") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            if not allow_priv:
                return False
            continue
        # Public IP: allow (user opted into webhooks)
        continue
    return True


def validate_webhook_url(url: str) -> tuple[bool, str]:
    """Reject SSRF-prone webhook targets. Returns (ok, reason)."""
    raw = (url or "").strip()
    if not raw:
        return False, "empty url"
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        return False, "scheme must be http or https"
    if not parsed.hostname:
        return False, "missing hostname"
    if parsed.username or parsed.password:
        return False, "credentials in URL not allowed"
    if not _host_is_safe_webhook_target(parsed.hostname):
        return False, "host unresolved or blocked (private/metadata); set SDN_WEBHOOK_ALLOW_PRIVATE=1 for LAN sinks"
    return True, "ok"


def security_headers() -> dict[str, str]:
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "SAMEORIGIN",
        "Referrer-Policy": "no-referrer",
        "Cache-Control": "no-store",
        "X-SDN-Lab": "research-console",
    }
