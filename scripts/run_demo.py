#!/usr/bin/env python
"""Cross-platform demo launcher: API + telemetry streamer."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description="Run live SDN-ITS demo")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--interval", type=float, default=1.5)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    env = {**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONPATH": str(PROJECT_ROOT / "src") + __import__("os").pathsep + str(PROJECT_ROOT)}

    controller = subprocess.Popen(
        [sys.executable, "-m", "api.app", "--port", str(args.port)],
        cwd=str(PROJECT_ROOT),
        env=env,
    )
    time.sleep(2)
    url = f"http://127.0.0.1:{args.port}/"
    if not args.no_browser:
        webbrowser.open(url)
    print(f"[+] Controller at {url}")
    print("[+] Starting telemetry streamer (Ctrl+C to stop)...")
    try:
        subprocess.call(
            [
                sys.executable,
                "-m",
                "sdn_its.simulation.traffic_generator",
                "--controller",
                f"http://127.0.0.1:{args.port}",
                "--interval",
                str(args.interval),
            ],
            cwd=str(PROJECT_ROOT),
            env=env,
        )
    finally:
        controller.terminate()
        controller.wait(timeout=5)
        print("[+] Demo stopped.")


if __name__ == "__main__":
    main()
