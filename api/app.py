"""Flask application factory for the SDN-ITS resilience API + dashboard."""

from __future__ import annotations

from flask import Flask

from api.middleware import register_middleware
from api.routes import register_routes
from sdn_its.controller.rest_api import ResilienceSDNController
from sdn_its.utils.paths import PROJECT_ROOT


def create_app(controller: ResilienceSDNController | None = None) -> Flask:
    template_folder = str(PROJECT_ROOT / "dashboard" / "templates")
    static_folder = str(PROJECT_ROOT / "dashboard" / "static")
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)

    if controller is None:
        controller = ResilienceSDNController(create_flask=False)
    controller.app = app
    app.extensions["sdn_controller"] = controller

    register_middleware(app)
    register_routes(app)
    return app


def main(port: int = 8080):
    controller = ResilienceSDNController(port=port)
    controller.run()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Start SDN Resilience Controller REST API")
    parser.add_argument("--port", type=int, default=8080, help="Controller REST API port")
    args = parser.parse_args()
    main(port=args.port)
