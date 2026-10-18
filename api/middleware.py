"""Flask middleware: timing, security headers, optional API token on mutating routes."""

from __future__ import annotations

import os
import time

from flask import Flask, g, jsonify, request

from sdn_its.utils.security import (
    api_token,
    extract_request_token,
    is_mutating_path,
    is_token_protected_path,
    require_api_token_for_lan,
    security_headers,
    token_ok,
)


def register_middleware(app: Flask) -> None:
    @app.before_request
    def _start_timer():
        g.request_start = time.perf_counter()

    @app.before_request
    def _enforce_api_token():
        from sdn_its.llm.hackathon_guard import hosted_demo_flag

        expected = api_token()
        ctrl = app.extensions.get("sdn_controller")
        host = getattr(ctrl, "host", None) or os.environ.get("SDN_BIND_HOST") or "127.0.0.1"
        protected = is_token_protected_path(request.path, request.method)
        # Hosted demo must not accept traffic without a token (startup also validates).
        if hosted_demo_flag() and not expected:
            return jsonify(
                {
                    "error": "misconfigured_hosted_demo",
                    "detail": "SDN_HOSTED_DEMO=1 requires SDN_API_TOKEN. Refusing protected requests.",
                }
            ), 503
        if not expected:
            if require_api_token_for_lan(str(host)) and is_mutating_path(request.path, request.method):
                # Soft-allow on non-hosted LAN lab only — stamp warning header.
                g.lan_token_missing = True
            return None
        if not protected:
            return None
        provided = extract_request_token(request.headers)
        if token_ok(provided, expected):
            return None
        # Do not echo provided tokens or Authorization headers in the response.
        return jsonify(
            {
                "error": "unauthorized",
                "detail": (
                    "Set Authorization: Bearer <SDN_API_TOKEN> or X-API-Token for "
                    "protected hackathon / mutating API calls."
                ),
            }
        ), 401

    @app.after_request
    def _add_security_and_timing(response):
        for k, v in security_headers().items():
            response.headers.setdefault(k, v)
        if getattr(g, "lan_token_missing", False):
            response.headers["X-SDN-Warning"] = "LAN bind without SDN_API_TOKEN"
        start = getattr(g, "request_start", None)
        if start is not None:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"
        return response
