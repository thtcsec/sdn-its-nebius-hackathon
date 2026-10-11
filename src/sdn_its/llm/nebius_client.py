"""Nebius Token Factory OpenAI-compatible client (real HTTP via requests)."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

import requests

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1"
DEFAULT_MODEL = "nvidia/Nemotron-3_5-Lightning"


class NebiusConfigError(RuntimeError):
    """Missing or invalid Nebius configuration."""


class NebiusAPIError(RuntimeError):
    """Token Factory HTTP or payload error."""

    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


@dataclass
class ChatCompletionResult:
    """Normalized chat completion (no secrets)."""

    content: str
    model: str
    finish_reason: str | None
    usage: dict[str, int]
    latency_ms: float
    raw_id: str | None = None
    evidence_class: str = "real_api"  # real_api | never fabricate
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
    key = (explicit if explicit is not None else os.environ.get("NEBIUS_API_KEY") or "").strip()
    if not key:
        raise NebiusConfigError(
            "NEBIUS_API_KEY is not set. Create a Token Factory key and export it "
            "(never commit). See configs/nebius.yaml and .env.example."
        )
    return key


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
        self.base_url = (self.base_url or DEFAULT_BASE_URL).rstrip("/")
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
        resp = self._session.get(url, headers=self._headers(), timeout=self.timeout_s)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        if resp.status_code >= 400:
            raise NebiusAPIError(
                f"list_models failed HTTP {resp.status_code}",
                status_code=resp.status_code,
                body=_safe_body(resp),
            )
        data = resp.json()
        if isinstance(data, dict):
            data = {**data, "_client_latency_ms": latency_ms, "_evidence_class": "real_api"}
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
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        t0 = time.perf_counter()
        resp = self._session.post(url, headers=self._headers(), json=payload, timeout=self.timeout_s)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        body = _safe_body(resp)
        if resp.status_code >= 400:
            raise NebiusAPIError(
                f"chat_completions failed HTTP {resp.status_code}",
                status_code=resp.status_code,
                body=body,
            )
        if not isinstance(body, dict):
            raise NebiusAPIError("chat_completions response is not a JSON object", body=body)

        choices = body.get("choices") or []
        if not choices:
            raise NebiusAPIError("chat_completions returned no choices", body=body)
        message = (choices[0] or {}).get("message") or {}
        content = message.get("content")
        if content is None:
            raise NebiusAPIError("chat_completions message.content missing", body=body)

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
