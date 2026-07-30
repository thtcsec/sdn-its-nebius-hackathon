"""Flask middleware hooks."""

from __future__ import annotations

from flask import Flask, g
import time


def register_middleware(app: Flask) -> None:
    @app.before_request
    def _start_timer():
        g.request_start = time.perf_counter()

    @app.after_request
    def _add_timing_header(response):
        start = getattr(g, "request_start", None)
        if start is not None:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"
        return response
