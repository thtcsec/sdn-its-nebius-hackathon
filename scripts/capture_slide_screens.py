#!/usr/bin/env python
"""Capture slide-ready screenshots with live camera + fusion demo beats."""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "images" / "slides"
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
    time.sleep(0.2)


def shot(page, name: str) -> Path:
    path = OUT / name
    page.screenshot(path=str(path), full_page=False)
    im = Image.open(path)
    # also write a compressed jpg for slides
    jpg = path.with_suffix(".jpg")
    im.convert("RGB").save(jpg, quality=85, optimize=True)
    print(f"[+] {name} {im.size[0]}x{im.size[1]} png={path.stat().st_size//1024}KB jpg={jpg.stat().st_size//1024}KB")
    return path


def api_prep() -> dict:
    s = requests.post(
        BASE + "/api/v1/settings",
        json={"lab_mode": False, "scenario_override": True},
        timeout=30,
    ).json()
    requests.post(BASE + "/api/v1/camera/scenario", json={"scenario": "idle"}, timeout=30)
    cam = requests.get(BASE + "/api/v1/camera", timeout=60).json()
    st = requests.get(BASE + "/api/v1/status", timeout=30).json()
    return {"settings": s, "camera": cam, "status": st}


def main() -> None:
    prep = api_prep()
    agg = (prep["camera"].get("aggregate") or {})
    meta = {
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "live_rtsp": agg.get("live_rtsp"),
        "frame_fresh": agg.get("frame_fresh"),
        "stream_available": agg.get("stream_available"),
        "source": agg.get("source"),
        "tracks": agg.get("visible_vehicle_tracks"),
        "physical_label": agg.get("physical_label"),
        "of_backend": prep["status"].get("of_backend"),
        "network_evidence": prep["status"].get("network_evidence"),
        "model_loaded": prep["status"].get("model_loaded"),
        "cameras": [
            {
                "camera_id": c.get("camera_id"),
                "connected": c.get("connected"),
                "preview_mtime": c.get("preview_mtime"),
                "rtsp_host": (c.get("rtsp_url_redacted") or "").split("@")[-1].split("/")[0]
                if c.get("rtsp_url_redacted")
                else None,
            }
            for c in (prep["camera"].get("cameras") or [])
        ],
    }
    (OUT / "capture_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print("meta", json.dumps(meta, indent=2))

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        page = context.new_page()
        page.goto(BASE, wait_until="networkidle", timeout=90000)
        time.sleep(2.5)
        close_settings(page)

        # Slide: overview / evidence strip
        page.evaluate("window.scrollTo(0,0)")
        shot(page, "slide_01_console_overview.png")

        # Slide: live cameras
        page.evaluate(
            """() => {
              const el = document.getElementById('fusion-row') || document.querySelector('[aria-label*=\"Camera\"]');
              if (el) el.scrollIntoView({block:'start'});
            }"""
        )
        time.sleep(1.0)
        # ensure live detector mode
        btn = page.locator('button[data-cam-scen="idle"]')
        if btn.count():
            btn.first.click()
            time.sleep(2.0)
        shot(page, "slide_02_live_cameras.png")

        # Slide: rush preserve fusion
        page.locator('button[data-cam-scen="rush"]').first.click()
        time.sleep(0.8)
        page.evaluate("window.scrollTo(0,0)")
        page.locator('button.scenario-btn.ddos[onclick*="DDoS"]').click()
        # then force rush cam + low dominance via API for preserve clarity
        requests.post(BASE + "/api/v1/camera/scenario", json={"scenario": "rush"}, timeout=30)
        requests.post(
            BASE + "/api/v1/anomaly_alert",
            json={
                "alert_id": "SLIDE-RUSH",
                "dpid": "0000000000000001",
                "src_ip": "10.0.0.12",
                "attack_type": "DDoS_PacketIn_Flood",
                "prediction": "DDoS_PacketIn_Flood",
                "reconstruction_error": 110,
                "confidence": 0.98,
                "cooldown_seconds": 0,
                "camera_scenario": "rush",
                "source_dominance": 0.30,
                "packet_in_delta_pct": 220,
                "distributed_sources": True,
            },
            timeout=30,
        )
        time.sleep(1.2)
        page.reload(wait_until="networkidle")
        time.sleep(1.5)
        close_settings(page)
        page.evaluate(
            """() => {
              const el = document.getElementById('panel-fusion') || document.getElementById('fusion-row');
              if (el) el.scrollIntoView({block:'center'});
            }"""
        )
        time.sleep(0.8)
        shot(page, "slide_03_fusion_rush_preserve.png")

        # Slide: contain under stable cam
        requests.post(BASE + "/api/v1/camera/scenario", json={"scenario": "attack_physical_stable"}, timeout=30)
        requests.post(
            BASE + "/api/v1/anomaly_alert",
            json={
                "alert_id": "SLIDE-DROP",
                "dpid": "0000000000000001",
                "src_ip": "10.0.0.15",
                "attack_type": "DDoS_PacketIn_Flood",
                "prediction": "DDoS_PacketIn_Flood",
                "reconstruction_error": 130,
                "confidence": 0.98,
                "cooldown_seconds": 12,
                "camera_scenario": "attack_physical_stable",
                "source_dominance": 0.85,
                "packet_in_delta_pct": 420,
                "distributed_sources": False,
            },
            timeout=30,
        )
        page.evaluate("window.scrollTo(0,0)")
        page.locator('button.scenario-btn.ddos[onclick*="DDoS"]').click()
        time.sleep(1.4)
        shot(page, "slide_04_ddos_containment.png")
        page.evaluate(
            """() => {
              const h = [...document.querySelectorAll('h2')]
                .find(x => /Reconstruction error/i.test(x.textContent||''));
              if (h) h.scrollIntoView({block:'start'});
            }"""
        )
        time.sleep(0.5)
        shot(page, "slide_05_re_chart_ddos.png")

        # Slide: rush-hour network button honesty
        page.evaluate("window.scrollTo(0,0)")
        page.locator('button.scenario-btn.rush[onclick*="RushHour"]').click()
        time.sleep(1.2)
        shot(page, "slide_06_rush_hour_network.png")

        browser.close()

    print(f"wrote slides to {OUT}")


if __name__ == "__main__":
    main()
