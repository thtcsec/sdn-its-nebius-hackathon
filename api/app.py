"""Flask application factory for the SDN-ITS resilience API + dashboard."""

from __future__ import annotations

from flask import Flask

from api.middleware import register_middleware
from api.routes import register_routes
from sdn_its.controller.rest_api import ResilienceSDNController
from sdn_its.utils.config import load_config
from sdn_its.utils.env import ensure_repo_env
from sdn_its.utils.paths import PROJECT_ROOT
from sdn_its.utils.security import resolve_bind_host


def create_app(controller: ResilienceSDNController | None = None) -> Flask:
    # Repo-root .env (NEBIUS_*), without overriding already-exported process env
    ensure_repo_env()
    template_folder = str(PROJECT_ROOT / "dashboard" / "templates")
    static_folder = str(PROJECT_ROOT / "dashboard" / "static")
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
    # Always re-read dashboard HTML/JS when files change (dev.ps1 runs with debug=False)
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.jinja_env.auto_reload = True
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    if controller is None:
        controller = ResilienceSDNController(create_flask=False)
    controller.app = app
    app.extensions["sdn_controller"] = controller

    register_middleware(app)
    register_routes(app)
    return app


def _default_host_port() -> tuple[str, int]:
    host = resolve_bind_host(None)
    port = 8080
    try:
        cfg = load_config("controller")
        if cfg.get("host"):
            host = resolve_bind_host(str(cfg["host"]))
        if cfg.get("port"):
            port = int(cfg["port"])
    except Exception:
        pass
    return host, port


def main(host: str | None = None, port: int | None = None):
    cfg_host, cfg_port = _default_host_port()
    controller = ResilienceSDNController(
        host=host if host is not None else cfg_host,
        port=port if port is not None else cfg_port,
    )
    controller.run()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Start SDN Resilience Controller REST API")
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Bind host (default: configs/controller.yaml or SDN_BIND_HOST / 127.0.0.1)",
    )
    parser.add_argument("--port", type=int, default=None, help="Controller REST API port")
    args = parser.parse_args()
    main(host=args.host, port=args.port)
