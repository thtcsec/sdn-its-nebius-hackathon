#!/usr/bin/env python
"""Capture current ops-console screenshots for the IEDE project report."""

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
    print(f"[+] {path.relative_to(ROOT)} ({path.stat().st_size // 1024} KB)")
    return path


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1.25)
        page = context.new_page()
        page.goto(BASE, wait_until="networkidle", timeout=60000)
        time.sleep(2.0)

        try:
            if page.locator("#settings-drawer.open").count():
                page.click("#settings-close")
                time.sleep(0.4)
        except Exception:
            pass

        # Ensure English labels if toggle exists
        try:
            lang = page.locator("#btn-lang")
            if lang.count() and "EN" in (lang.inner_text() or ""):
                # button shows target language; if it says EN, current is VI → click to EN
                lang.click()
                time.sleep(0.4)
        except Exception:
            pass

        shot(page, "fig01_console_overview.png", full_page=True)

        # Network DDoS contain
        page.get_by_text("PacketIn flood", exact=False).first.click()
        time.sleep(1.4)
        shot(page, "fig02_ddos_containment.png", full_page=True)

        # Settings
        page.click("#btn-settings")
        time.sleep(0.7)
        shot(page, "fig03_settings_drawer.png")
        page.click("#settings-close")
        time.sleep(0.4)

        # Rush-hour network label
        page.get_by_text("Rush-hour surge", exact=False).first.click()
        time.sleep(1.2)
        shot(page, "fig04_rush_hour_preserve.png", full_page=True)

        # Replay
        try:
            page.select_option("#replay-script", "ddos_cycle")
            page.click("#btn-replay")
            time.sleep(4.5)
            shot(page, "fig05_replay_timeline.png", full_page=True)
            page.click("#btn-replay-stop")
        except Exception as exc:
            print(f"[!] replay shot skipped: {exc}")

        # Topology / bottom
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(0.5)
        shot(page, "fig06_topology_events.png")

        # Camera panel — scroll to cameras, set rush synth
        page.locator("#panel-cameras").scroll_into_view_if_needed()
        time.sleep(0.5)
        page.locator('[data-cam-scen="rush"]').click()
        time.sleep(1.2)
        shot(page, "fig07_camera_tracks.png")

        # Fusion preserve: cam rush + network flood mid view
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(0.3)
        page.get_by_text("PacketIn flood", exact=False).first.click()
        time.sleep(0.8)
        page.locator("#panel-cameras").scroll_into_view_if_needed()
        time.sleep(0.8)
        shot(page, "fig08_fusion_camera.png", full_page=False)

        # Also capture cameras + fusion explain area taller
        page.locator("#panel-cameras").scroll_into_view_if_needed()
        time.sleep(0.3)
        shot(page, "fig08_fusion_camera.png")

        browser.close()
    print("[+] Screenshots ready in assets/images/report/")


if __name__ == "__main__":
    main()
