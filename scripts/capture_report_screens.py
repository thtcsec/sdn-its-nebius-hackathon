#!/usr/bin/env python
"""Capture annotated ops-console screenshots for the IEDE project report."""

from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "images" / "report"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:8080"


def shot(page, name: str, full_page: bool = False) -> Path:
    path = OUT / name
    page.screenshot(path=str(path), full_page=full_page)
    print(f"[+] {path.relative_to(ROOT)}")
    return path


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1.25)
        page = context.new_page()
        page.goto(BASE, wait_until="networkidle")
        time.sleep(1.5)

        # Close settings if open
        try:
            if page.locator("#settings-drawer.open").count():
                page.click("#settings-close")
                time.sleep(0.4)
        except Exception:
            pass

        shot(page, "fig01_console_overview.png", full_page=True)

        # DDoS contain view
        page.click("text=PacketIn flood (DDoS)")
        time.sleep(1.2)
        shot(page, "fig02_ddos_containment.png", full_page=True)

        # Settings drawer
        page.click("#btn-settings")
        time.sleep(0.6)
        shot(page, "fig03_settings_drawer.png")
        page.click("#settings-close")
        time.sleep(0.4)

        # Rush-hour benign preserve
        page.click("text=Rush-hour surge")
        time.sleep(1.0)
        shot(page, "fig04_rush_hour_preserve.png", full_page=True)

        # Replay start
        page.select_option("#replay-script", "ddos_cycle")
        page.click("#btn-replay")
        time.sleep(4.5)
        shot(page, "fig05_replay_timeline.png", full_page=True)
        page.click("#btn-replay-stop")

        # Topology + event stream crop via full page already covered; take focused scroll
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(0.5)
        shot(page, "fig06_topology_events.png")

        browser.close()
    print("[+] Screenshots ready in assets/images/report/")


if __name__ == "__main__":
    main()
