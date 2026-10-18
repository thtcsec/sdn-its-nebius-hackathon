"""Flask helpers: shared model-route enforcement for JunctionTrace."""

from __future__ import annotations

from typing import Any

from flask import Request, jsonify

from sdn_its.llm.hackathon_guard import (
    GuardDecision,
    client_rate_identity,
    get_inference_guard,
    legacy_model_routes_disabled,
    resolve_request_safety_flags,
)


def request_client_key(req: Request) -> str:
    return client_rate_identity(
        remote_addr=req.remote_addr,
        x_forwarded_for=req.headers.get("X-Forwarded-For"),
    )


def legacy_disabled_response():
    return (
        jsonify(
            {
                "error": "legacy_route_disabled",
                "detail": (
                    "Hosted demo disables /api/v1/hackathon/run and /investigate. "
                    "Use POST /api/v1/hackathon/multistep with Authorization."
                ),
                "ok": False,
                "evidence_class": "blocked_guard",
            }
        ),
        410,
    )


def guard_reject_response(decision: GuardDecision):
    resp = jsonify(
        {
            "error": decision.error,
            "detail": decision.detail,
            "ok": False,
            "evidence_class": "blocked_guard",
        }
    )
    resp.status_code = decision.status
    for hk, hv in (decision.headers or {}).items():
        resp.headers[hk] = hv
    return resp


def begin_real_if_needed(req: Request, mode: str) -> tuple[GuardDecision | None, Any]:
    """If mode==real, admit a shared quota slot. Returns (decision|None, reject_response|None)."""
    if mode != "real":
        return None, None
    if legacy_model_routes_disabled() and False:
        pass
    guard = get_inference_guard()
    decision = guard.admit_real(request_client_key(req))
    if not decision.ok:
        return decision, guard_reject_response(decision)
    return decision, None


def finish_real(decision: GuardDecision | None, *, estimated_usd: float | None = None, failed: bool = False) -> None:
    if decision is None or not decision.ok or not decision.reservation_id:
        return
    get_inference_guard().settle(
        decision.reservation_id,
        estimated_usd=estimated_usd,
        failed=failed,
    )


def safety_from_body(data: dict[str, Any] | None) -> dict[str, Any]:
    return resolve_request_safety_flags(data)
