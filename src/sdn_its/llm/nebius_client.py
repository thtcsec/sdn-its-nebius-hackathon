"""Nebius Token Factory OpenAI-compatible client (real HTTP via requests)."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

import requests

from sdn_its.utils.env import ensure_repo_env, getenv_stripped

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1"
# Nano follows structured JSON reliably; Lightning often spends the budget on CoT.
DEFAULT_MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
# Used when the primary model returns unparseable investigation output
FALLBACK_INVESTIGATION_MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"

# Error classes for evidence / exit handling (never include secrets)
ERROR_AUTH = "authentication"
ERROR_MODEL = "model_availability"
ERROR_BILLING = "billing"
ERROR_NETWORK = "network"
ERROR_SCHEMA = "schema"
ERROR_CONFIG = "config"
ERROR_UNKNOWN = "unknown"


class NebiusConfigError(RuntimeError):
    """Missing or invalid Nebius configuration."""

    error_class = ERROR_CONFIG


class NebiusAPIError(RuntimeError):
    """Token Factory HTTP or payload error."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        body: Any = None,
        error_class: str = ERROR_UNKNOWN,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.error_class = error_class


@dataclass
class ChatCompletionResult:
    """Normalized chat completion (no secrets)."""

    content: str
    model: str
    finish_reason: str | None
    usage: dict[str, int]
    latency_ms: float
    raw_id: str | None = None
    evidence_class: str = "real_api"  # real_api | mocked_transport
    request_meta: dict[str, Any] = field(default_factory=dict)

    def estimated_cost_usd(
        self,
        *,
        input_per_million: float = 0.06,
        output_per_million: float = 0.24,
    ) -> float:
        """Rough USD estimate from public Token Factory list prices (Lightning default)."""
        prompt = int(self.usage.get("prompt_tokens") or 0)
        completion = int(self.usage.get("completion_tokens") or 0)
        return (prompt / 1_000_000.0) * input_per_million + (completion / 1_000_000.0) * output_per_million


def load_api_key(explicit: str | None = None) -> str:
    """Resolve API key: explicit arg → process env / repo-root `.env` (env wins over file)."""
    ensure_repo_env()
    if explicit is not None:
        key = explicit.strip()
    else:
        key = (getenv_stripped("NEBIUS_API_KEY") or "").strip()
    if not key:
        raise NebiusConfigError(
            "NEBIUS_API_KEY is not set. Add it to the repository-root .env "
            "(gitignored) or export it in the process environment. "
            "See .env.example and configs/nebius.yaml."
        )
    return key


def resolve_base_url(explicit: str | None = None) -> str:
    ensure_repo_env()
    if explicit:
        return explicit.rstrip("/")
    return (getenv_stripped("NEBIUS_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def resolve_model(explicit: str | None = None) -> str:
    ensure_repo_env()
    if explicit:
        return explicit.strip()
    return (getenv_stripped("NEBIUS_MODEL") or DEFAULT_MODEL).strip()


def classify_http_error(status_code: int | None, body: Any) -> str:
    """Map provider failures to stable error classes (no secrets)."""
    text = ""
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            text = f"{err.get('type', '')} {err.get('code', '')} {err.get('message', '')}".lower()
        else:
            text = str(body).lower()
    elif body is not None:
        text = str(body).lower()

    if status_code in {401, 403}:
        return ERROR_AUTH
    if status_code == 402 or any(t in text for t in ("insufficient", "quota", "billing", "payment", "balance", "credit")):
        return ERROR_BILLING
    if status_code == 404 or any(
        t in text for t in ("model_not_found", "does not exist", "unknown model", "invalid model", "not found")
    ):
        if "model" in text or status_code == 404:
            return ERROR_MODEL
    if status_code == 429 and any(t in text for t in ("quota", "billing", "credit")):
        return ERROR_BILLING
    if status_code in {408, 502, 503, 504} or status_code is None:
        return ERROR_NETWORK
    if status_code in {400, 422}:
        if "model" in text:
            return ERROR_MODEL
        return ERROR_SCHEMA
    return ERROR_UNKNOWN


_SECRET_KEY_NAMES = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "access_token",
        "refresh_token",
        "secret",
        "password",
        "bearer",
        "nebius_api_key",
    }
)


def redact_body(body: Any) -> Any:
    """Strip secret-bearing fields from error bodies before persistence.

    Does not touch usage counters like ``prompt_tokens`` / ``completion_tokens``.
    """
    if not isinstance(body, dict):
        return body
    out: dict[str, Any] = {}
    for k, v in body.items():
        lk = str(k).lower().replace("-", "_")
        if lk in _SECRET_KEY_NAMES or lk.endswith("_api_key") or lk.endswith("_secret"):
            out[k] = "<redacted>"
        elif isinstance(v, dict):
            out[k] = redact_body(v)
        else:
            out[k] = v
    return out


@dataclass
class NebiusTokenFactoryClient:
    """Minimal chat.completions client for Nebius Token Factory."""

    api_key: str | None = None
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    timeout_s: float = 60.0
    session: requests.Session | None = None
    # Label for evidence artifacts: use mocked_transport when injecting a fake session
    evidence_class: str = "real_api"

    def __post_init__(self) -> None:
        ensure_repo_env()
        self.base_url = resolve_base_url(self.base_url if self.base_url != DEFAULT_BASE_URL else None)
        # If caller passed default sentinel, allow env/config override
        if self.model == DEFAULT_MODEL:
            self.model = resolve_model(None)
        else:
            self.model = resolve_model(self.model)
        self.base_url = self.base_url.rstrip("/")
        self._session = self.session or requests.Session()
        if self.session is not None and self.evidence_class == "real_api":
            # Custom sessions in unit tests are not cloud proof
            self.evidence_class = "mocked_transport"

    def _headers(self) -> dict[str, str]:
        key = load_api_key(self.api_key)
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def list_models(self) -> dict[str, Any]:
        """GET /v1/models — authenticated; returns parsed JSON (may be large)."""
        url = f"{self.base_url}/models"
        t0 = time.perf_counter()
        try:
            resp = self._session.get(url, headers=self._headers(), timeout=self.timeout_s)
        except requests.RequestException as exc:
            raise NebiusAPIError(
                f"list_models network error: {type(exc).__name__}",
                status_code=None,
                body={"exception": type(exc).__name__},
                error_class=ERROR_NETWORK,
            ) from exc
        latency_ms = (time.perf_counter() - t0) * 1000.0
        if resp.status_code >= 400:
            body = redact_body(_safe_body(resp))
            raise NebiusAPIError(
                f"list_models failed HTTP {resp.status_code}",
                status_code=resp.status_code,
                body=body,
                error_class=classify_http_error(resp.status_code, body),
            )
        data = resp.json()
        if isinstance(data, dict):
            data = {**data, "_client_latency_ms": latency_ms, "_evidence_class": self.evidence_class}
        return data

    def chat_completions(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        response_format: dict[str, Any] | None = None,
    ) -> ChatCompletionResult:
        """POST /v1/chat/completions — real network call when key is present."""
        url = f"{self.base_url}/chat/completions"
        chosen_model = resolve_model(model) if model else self.model
        payload: dict[str, Any] = {
            "model": chosen_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        t0 = time.perf_counter()
        try:
            resp = self._session.post(url, headers=self._headers(), json=payload, timeout=self.timeout_s)
        except requests.RequestException as exc:
            raise NebiusAPIError(
                f"chat_completions network error: {type(exc).__name__}",
                status_code=None,
                body={"exception": type(exc).__name__},
                error_class=ERROR_NETWORK,
            ) from exc
        latency_ms = (time.perf_counter() - t0) * 1000.0
        body = redact_body(_safe_body(resp))
        if resp.status_code >= 400:
            raise NebiusAPIError(
                f"chat_completions failed HTTP {resp.status_code}",
                status_code=resp.status_code,
                body=body,
                error_class=classify_http_error(resp.status_code, body),
            )
        if not isinstance(body, dict):
            raise NebiusAPIError(
                "chat_completions response is not a JSON object",
                body=body,
                error_class=ERROR_SCHEMA,
            )

        choices = body.get("choices") or []
        if not choices:
            raise NebiusAPIError(
                "chat_completions returned no choices",
                body=body,
                error_class=ERROR_SCHEMA,
            )
        message = (choices[0] or {}).get("message") or {}
        content = message.get("content")
        # Some Nemotron servings put draft text in ``reasoning`` with content=null
        if content is None or (isinstance(content, str) and not content.strip()):
            reasoning = message.get("reasoning")
            if isinstance(reasoning, str) and reasoning.strip():
                content = reasoning
        if content is None or (isinstance(content, str) and not str(content).strip()):
            raise NebiusAPIError(
                "chat_completions message.content/reasoning missing",
                body=body,
                error_class=ERROR_SCHEMA,
                status_code=resp.status_code,
            )

        usage_raw = body.get("usage") or {}
        usage = {
            "prompt_tokens": int(usage_raw.get("prompt_tokens") or 0),
            "completion_tokens": int(usage_raw.get("completion_tokens") or 0),
            "total_tokens": int(usage_raw.get("total_tokens") or 0),
        }
        return ChatCompletionResult(
            content=str(content),
            model=str(body.get("model") or payload["model"]),
            finish_reason=(choices[0] or {}).get("finish_reason"),
            usage=usage,
            latency_ms=latency_ms,
            raw_id=body.get("id"),
            evidence_class=self.evidence_class,
            request_meta={
                "base_url": self.base_url,
                "requested_model": payload["model"],
                "http_status": resp.status_code,
            },
        )


def _safe_body(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        text = (resp.text or "")[:500]
        return {"_non_json_body_preview": text}
