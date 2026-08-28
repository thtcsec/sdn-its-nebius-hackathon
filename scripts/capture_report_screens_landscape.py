#!/usr/bin/env python
"""Capture landscape 1920x1080 dashboard screenshots (Chrome channel)."""

from __future__ import annotations

import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "images" / "report"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:8080"


def close_settings(page) -> None:
    page.evaluate(
        """() => {
          const d = document.getElementById('settings-drawer');
          if (d) { d.classList.remove('open'); d.setAttribute('aria-hidden','true'); }
          const b = document.getElementById('settings-backdrop');
          if (b) b.classList.remove('open');
        }"""
    )
    time.sleep(0.3)


def shot(page, name: str, full_page: bool = False) -> Path:
    path = OUT / name
    page.screenshot(path=str(path), full_page=full_page)
    im = Image.open(path)
    print(f"[+] {name} {im.size[0]}x{im.size[1]} ({path.stat().st_size // 1024} KB)")
    return path


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(
            # Match dashboard .shell max-width so we don't get empty side gutters
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2.0,
        )
        page = context.new_page()
        page.goto(BASE, wait_until="networkidle", timeout=60000)
        time.sleep(2.0)
        close_settings(page)

        shot(page, "fig01_console_overview.png")

        page.locator('button.scenario-btn.ddos[onclick*="DDoS"]').click()
        time.sleep(1.4)
        shot(page, "fig02_ddos_containment.png")

        # scroll mid to include chart + rules for a richer containment plate
        page.evaluate(
            """() => {
              const h = [...document.querySelectorAll('h2')]
                .find(x => /Reconstruction error/i.test(x.textContent||''));
              if (h) h.scrollIntoView({block:'start'});
            }"""
        )
        time.sleep(0.5)
        shot(page, "fig02b_re_chart_ddos.png")

        page.evaluate("window.scrollTo(0,0)")
        time.sleep(0.3)
        page.click("#btn-settings")
        time.sleep(0.8)
        shot(page, "fig03_settings_drawer.png")
        close_settings(page)

        page.locator('button.scenario-btn.rush[onclick*="RushHour"]').click()
        time.sleep(1.2)
        shot(page, "fig04_rush_hour_preserve.png")

        page.select_option("#replay-script", "ddos_cycle")
        page.click("#btn-replay")
        time.sleep(4.8)
        page.evaluate(
            """() => {
              const h = [...document.querySelectorAll('h2')]
                .find(x => /Reconstruction error/i.test(x.textContent||''));
              if (h) h.scrollIntoView({block:'start'});
            }"""
        )
        time.sleep(0.4)
        shot(page, "fig05_replay_timeline.png")
        page.click("#btn-replay-stop")

        page.locator("#panel-cameras").scroll_into_view_if_needed()
        time.sleep(0.4)
        page.locator('[data-cam-scen="rush"]').click()
        time.sleep(1.2)
        shot(page, "fig07_camera_tracks.png")

        page.locator('button.scenario-btn.ddos[onclick*="DDoS"]').click()
        time.sleep(1.0)
        page.locator("#panel-cameras").scroll_into_view_if_needed()
        time.sleep(0.5)
        shot(page, "fig08_fusion_camera.png")

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(0.6)
        shot(page, "fig06_topology_events.png")

        # full-page landscape strip for appendix gallery
        page.evaluate("window.scrollTo(0,0)")
        time.sleep(0.3)
        close_settings(page)
        shot(page, "fig01_console_overview_full.png", full_page=True)

        browser.close()
    print("[+] landscape screenshots ready")


if __name__ == "__main__":
    main()
