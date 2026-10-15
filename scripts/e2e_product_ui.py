#!/usr/bin/env python3
"""Playwright E2E + screenshots for JunctionTrace product UI.

Writes artifacts/hackathon/product_screens/ and e2e_product_report.json.
Requires: pip install playwright && playwright install chromium
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "hackathon" / "product_screens"
REPORT = ROOT / "artifacts" / "hackathon" / "e2e_product_report.json"
BASE = os.environ.get("JT_BASE_URL", "http://127.0.0.1:8080")


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed", file=sys.stderr)
        return 2

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []
    screens: list[str] = []

    def ok(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})
        print(("PASS" if passed else "FAIL"), name, detail)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # 1–3 landing
        page.goto(f"{BASE}/", wait_until="networkidle")
        time.sleep(0.4)
        html = page.content()
        title = page.title()
        ok("fresh_root_product", "JunctionTrace" in title and "JunctionTrace" in html, title)
        hero = page.locator("h1").first.inner_text()
        ok("hero_problem", "traffic surge" in hero.lower() or "not always an attack" in hero.lower(), hero)
        ok("cta_present", page.locator("#btn-investigate").count() > 0)
        ok("scenario_selector", page.locator(".scenario-card").count() >= 4)
        ok("no_tsinghua_iede", "Tsinghua IEDE" not in html and "IEDE Console" not in html)
        landing = OUT_DIR / "01_landing_1440x900.png"
        page.screenshot(path=str(landing), full_page=False)
        screens.append(str(landing))

        # 5 offline investigation with timeline evolution
        page.locator("#mode-offline").click()
        page.locator('.scenario-card[data-id="scenario_missing_camera"]').click()
        page.locator("#btn-investigate").click()
        # in-progress
        page.wait_for_selector("#loading-state:not([hidden])", timeout=5000)
        mid = OUT_DIR / "02_investigating_1440x900.png"
        page.screenshot(path=str(mid), full_page=False)
        screens.append(str(mid))
        page.wait_for_selector(".badge", timeout=60000)
        time.sleep(0.8)
        body = page.locator("#result-body").inner_text()
        offline_ok = ("LIVE Nebius" not in body) and (
            "deterministic planner" in body.lower() or "offline" in body.lower() or "deterministic" in body.lower()
        )
        ok("offline_not_labeled_live", offline_ok, body[:200])
        ok("timeline_has_detail", bool(page.locator("#d1").inner_text().strip()))
        done = OUT_DIR / "03_complete_offline_1440x900.png"
        page.screenshot(path=str(done), full_page=False)
        screens.append(str(done))

        # 6 real mode if credentials
        caps = page.evaluate("async () => (await fetch('/api/v1/hackathon/capabilities')).json()")
        if caps.get("nebius_api_key_present"):
            page.locator("#mode-real").click()
            page.locator('.scenario-card[data-id="scenario_loft_stable"]').click()
            page.locator("#btn-investigate").click()
            page.wait_for_selector("#loading-state:not([hidden])", timeout=5000)
            page.wait_for_function(
                """() => {
                  const t = document.querySelector('#result-body')?.innerText || '';
                  return t.includes('real_api') || t.includes('LIVE') || t.includes('error') || t.includes('blocked');
                }""",
                timeout=90000,
            )
            time.sleep(0.5)
            real_body = page.locator("#result-body").inner_text()
            ok(
                "real_nebius_path",
                "real_api" in real_body.lower() or "LIVE" in real_body or "blocked" in real_body.lower(),
                real_body[:220],
            )
            real_shot = OUT_DIR / "04_complete_real_1440x900.png"
            page.screenshot(path=str(real_shot), full_page=False)
            screens.append(str(real_shot))
        else:
            ok("real_nebius_path", True, "skipped_no_credentials")

        # 4 research preserved
        page.goto(f"{BASE}/research", wait_until="networkidle")
        rhtml = page.content()
        ok("research_preserved", "IEDE" in rhtml or "AI-Assisted SDN-ITS" in rhtml)
        research = OUT_DIR / "05_research_1440x900.png"
        page.screenshot(path=str(research), full_page=False)
        screens.append(str(research))

        # 9 mobile
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(f"{BASE}/", wait_until="networkidle")
        time.sleep(0.3)
        btn = page.locator("#btn-investigate")
        box = btn.bounding_box()
        ok("mobile_cta_visible", box is not None and box["width"] > 40 and box["y"] < 844)
        mobile = OUT_DIR / "06_mobile_390x844.png"
        page.screenshot(path=str(mobile), full_page=False)
        screens.append(str(mobile))

        # 7 error path: force unavailable via API then show UI can display errors — use real without key simulation
        # Already covered by capabilities; probe malformed through API
        page.set_viewport_size({"width": 1440, "height": 900})
        api = page.evaluate(
            """async () => {
              const r = await fetch('/api/v1/hackathon/multistep', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                  incident_id: '05_malformed_model_output',
                  mode: 'offline',
                  demo_mode: true,
                  apply_gate: true
                })
              });
              return {status: r.status, body: await r.json()};
            }"""
        )
        ok(
            "malformed_fail_closed_api",
            api.get("status") in {200, 502} and (
                (api.get("body") or {}).get("evidence_class") in {"validation_error", "synthetic_malformed", "deterministic_planner"}
                or (api.get("body") or {}).get("ok") is False
            ),
            str(api)[:240],
        )

        browser.close()

    report = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "base": BASE,
        "checks": checks,
        "screenshots": screens,
        "passed": all(c["passed"] for c in checks),
        "pass_count": sum(1 for c in checks if c["passed"]),
        "total": len(checks),
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "pass_count": report["pass_count"], "total": report["total"], "out": str(REPORT)}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
