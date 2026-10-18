#!/usr/bin/env python3
"""Playwright E2E + screenshots for JunctionTrace product UI.

Trust rules:
- Real-mode MUST NOT PASS when evidence_class is blocked_* or result is "blocked".
- Missing Nebius credentials → SKIPPED / NOT_RUN (not PASS).
- Real API PASS requires evidence_class=real_api, selected tools, valid conclusion, LIVE labeling.
- Deterministic / mocked / real_api counts are reported separately.
- Process exit code nonzero when any mandatory (non-skipped) check fails.

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
JUDGE_TOKEN = (os.environ.get("SDN_API_TOKEN") or os.environ.get("JT_JUDGE_TOKEN") or "").strip()

# XSS payload — must appear as text, never as executable/script DOM
XSS_MARKER = "XSS_JT_PROBE_7f3a"
XSS_PAYLOAD = f'<img src=x onerror=window.__jt_xss=1><script>window.__jt_xss=1</script>{XSS_MARKER}'


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed", file=sys.stderr)
        return 2

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []
    screens: list[str] = []
    caps: dict = {}

    def record(name: str, status: str, detail: str = "", bucket: str = "deterministic") -> None:
        """status: PASS | FAIL | SKIPPED | NOT_RUN"""
        st = status.upper()
        checks.append({"name": name, "status": st, "passed": st == "PASS", "skipped": st in {"SKIPPED", "NOT_RUN"}, "detail": detail, "bucket": bucket})
        print(st, name, detail)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # —— Landing / viewport density ——
        page.goto(f"{BASE}/", wait_until="networkidle")
        time.sleep(0.4)
        html = page.content()
        title = page.title()
        record(
            "fresh_root_product",
            "PASS" if ("JunctionTrace" in title and "JunctionTrace" in html) else "FAIL",
            title,
            "deterministic",
        )
        hero = page.locator("h1").first.inner_text()
        record(
            "hero_problem",
            "PASS" if ("traffic surge" in hero.lower() or "not always an attack" in hero.lower()) else "FAIL",
            hero,
            "deterministic",
        )
        record(
            "cta_present",
            "PASS" if page.locator("#btn-investigate").count() > 0 else "FAIL",
            bucket="deterministic",
        )
        sc_count = page.locator(".scenario-card").count()
        record("scenario_selector", "PASS" if sc_count >= 4 else "FAIL", f"count={sc_count}", "deterministic")
        record(
            "no_tsinghua_iede",
            "PASS" if ("Tsinghua IEDE" not in html and "IEDE Console" not in html) else "FAIL",
            bucket="deterministic",
        )
        # First viewport: scenarios should start above fold at 1440x900
        first_sc = page.locator(".scenario-card").first.bounding_box()
        record(
            "scenarios_in_first_viewport",
            "PASS" if first_sc and first_sc["y"] < 820 else "FAIL",
            f"y={first_sc['y'] if first_sc else None}",
            "deterministic",
        )
        # Scenario B must not claim "Credible cyberattack" as a certainty
        b_title = page.locator('.scenario-card[data-id="scenario_loft_stable"] h3').inner_text()
        record(
            "scenario_b_honest_label",
            "PASS" if "credible cyberattack" not in b_title.lower() else "FAIL",
            b_title,
            "deterministic",
        )
        landing = OUT_DIR / "01_landing_1440x900.png"
        page.screenshot(path=str(landing), full_page=False)
        screens.append(str(landing))

        # —— Offline investigation ——
        page.locator("#mode-offline").click()
        page.locator('.scenario-card[data-id="scenario_missing_camera"]').click()
        page.locator("#btn-investigate").click()
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
        record("offline_not_labeled_live", "PASS" if offline_ok else "FAIL", body[:200], "deterministic")
        record(
            "timeline_has_detail",
            "PASS" if bool(page.locator("#d1").inner_text().strip()) else "FAIL",
            bucket="deterministic",
        )
        # Congestion case (Scenario A) — offline
        page.locator('.scenario-card[data-id="scenario_rush_vs_attack"]').click()
        page.locator("#btn-investigate").click()
        page.wait_for_selector(".badge", timeout=60000)
        time.sleep(0.5)
        cong = page.locator("#result-body").inner_text()
        record(
            "congestion_case_offline",
            "PASS" if ("Legitimate congestion" in cong or "rush" in cong.lower() or "deterministic" in cong.lower()) else "FAIL",
            cong[:180],
            "deterministic",
        )
        done = OUT_DIR / "03_complete_offline_1440x900.png"
        page.screenshot(path=str(done), full_page=False)
        screens.append(str(done))

        # —— Real mode (credential-gated) ——
        caps = page.evaluate("async () => (await fetch('/api/v1/hackathon/capabilities')).json()")
        creds = bool(caps.get("nebius_api_key_present"))
        if not creds:
            record(
                "real_nebius_path",
                "SKIPPED",
                "skipped_no_credentials — NOT_RUN (do not count as PASS)",
                "real_api",
            )
            # Still capture mode-toggle UI for evidence
            page.locator("#mode-real").click()
            real_shot = OUT_DIR / "04_complete_real_1440x900.png"
            page.screenshot(path=str(real_shot), full_page=False)
            screens.append(str(real_shot))
        else:
            if JUDGE_TOKEN:
                page.evaluate(
                    """(tok) => {
                      const el = document.getElementById('judge-token');
                      if (el) { el.value = tok; }
                    }""",
                    JUDGE_TOKEN,
                )
            page.locator("#mode-real").click()
            page.locator('.scenario-card[data-id="scenario_loft_stable"]').click()
            with page.expect_response(
                lambda r: "/api/v1/hackathon/multistep" in r.url and r.request.method == "POST",
                timeout=120000,
            ) as resp_info:
                page.locator("#btn-investigate").click()
            api_resp = resp_info.value
            try:
                api_body = api_resp.json()
            except Exception:
                api_body = {}
            page.wait_for_function(
                """() => {
                  const t = document.querySelector('#result-body')?.innerText || '';
                  return t.includes('real_api') || t.includes('LIVE') || t.includes('blocked')
                    || t.includes('error') || t.includes('budget') || t.includes('rate')
                    || t.includes('fail-closed') || t.includes('deterministic');
                }""",
                timeout=120000,
            )
            time.sleep(0.6)
            real_body = page.locator("#result-body").inner_text()
            ui_live = "real_api" in real_body.lower() or "LIVE Nebius" in real_body
            ui_blocked = ("blocked" in real_body.lower() or "blocked_" in str(api_body.get("evidence_class") or "")) and not ui_live
            ec = api_body.get("evidence_class") or ""
            tools = []
            for t in api_body.get("trace") or []:
                if t.get("phase") == "select_evidence_tool" and (t.get("detail") or {}).get("tool"):
                    tools.append(t["detail"]["tool"])
            if not tools:
                tools = list(api_body.get("tool_calls") or [])
            action = (api_body.get("recommendation") or {}).get("recommended_action")
            valid_action = action in {"observe", "rate_limit", "preserve", "escalate", "drop", "quarantine"}
            # Hard rule: blocked must never PASS
            if str(ec).startswith("blocked") or ui_blocked:
                record(
                    "real_nebius_path",
                    "FAIL",
                    f"blocked_or_guard ec={ec} ui_blocked={ui_blocked} body={real_body[:180]}",
                    "real_api",
                )
            elif ec == "real_api" and ui_live and tools and valid_action:
                record(
                    "real_nebius_path",
                    "PASS",
                    f"ec=real_api action={action} tools={tools[:4]}",
                    "real_api",
                )
            else:
                record(
                    "real_nebius_path",
                    "FAIL",
                    f"incomplete real evidence ec={ec} ui_live={ui_live} tools={tools} action={action}",
                    "real_api",
                )
            real_shot = OUT_DIR / "04_complete_real_1440x900.png"
            page.screenshot(path=str(real_shot), full_page=False)
            screens.append(str(real_shot))

        # —— Research preserved ——
        page.goto(f"{BASE}/research", wait_until="networkidle")
        rhtml = page.content()
        record(
            "research_preserved",
            "PASS" if ("IEDE" in rhtml or "AI-Assisted SDN-ITS" in rhtml) else "FAIL",
            bucket="deterministic",
        )
        research = OUT_DIR / "05_research_1440x900.png"
        page.screenshot(path=str(research), full_page=False)
        screens.append(str(research))

        # —— Mobile ——
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(f"{BASE}/", wait_until="networkidle")
        time.sleep(0.3)
        btn = page.locator("#btn-investigate")
        box = btn.bounding_box()
        record(
            "mobile_cta_visible",
            "PASS" if (box is not None and box["width"] > 40 and box["y"] < 844) else "FAIL",
            f"box={box}",
            "deterministic",
        )
        mobile = OUT_DIR / "06_mobile_390x844.png"
        page.screenshot(path=str(mobile), full_page=False)
        screens.append(str(mobile))

        # —— UI error path (malformed via actual UI + API) ——
        page.set_viewport_size({"width": 1440, "height": 900})
        page.goto(f"{BASE}/", wait_until="networkidle")
        api = page.evaluate(
            """async (tok) => {
              const headers = {'Content-Type': 'application/json'};
              if (tok) headers['X-API-Token'] = tok;
              const r = await fetch('/api/v1/hackathon/multistep', {
                method: 'POST',
                headers,
                body: JSON.stringify({
                  incident_id: '05_malformed_model_output',
                  mode: 'offline',
                  demo_mode: true,
                  apply_gate: true
                })
              });
              return {status: r.status, body: await r.json()};
            }""",
            JUDGE_TOKEN or None,
        )
        mal_ok = api.get("status") in {200, 502} and (
            (api.get("body") or {}).get("evidence_class")
            in {"validation_error", "synthetic_malformed", "deterministic_planner"}
            or (api.get("body") or {}).get("ok") is False
        )
        record("malformed_fail_closed_api", "PASS" if mal_ok else "FAIL", str(api)[:240], "mocked")

        # —— DOM XSS regression (textContent path) ——
        xss_ok = page.evaluate(
            """(payload) => {
              // Simulate renderResult path: rationale via textContent only
              const host = document.createElement('div');
              host.id = 'xss-host';
              document.body.appendChild(host);
              const p = document.createElement('p');
              p.className = 'rationale';
              p.textContent = payload;
              host.appendChild(p);
              const hasScriptChild = host.querySelector('script') !== null;
              const hasImg = host.querySelector('img') !== null;
              const textHas = (host.textContent || '').includes('XSS_JT_PROBE_7f3a');
              const execFlag = Boolean(window.__jt_xss);
              host.remove();
              return {hasScriptChild, hasImg, textHas, execFlag};
            }""",
            XSS_PAYLOAD,
        )
        # Also verify product JS has no innerHTML assignment
        js_src = page.evaluate(
            """async () => {
              const r = await fetch('/static/junctiontrace.js');
              return await r.text();
            }"""
        )
        no_inner = "innerHTML" not in js_src
        xss_pass = (
            no_inner
            and xss_ok.get("textHas")
            and not xss_ok.get("hasScriptChild")
            and not xss_ok.get("hasImg")
            and not xss_ok.get("execFlag")
        )
        record(
            "dom_xss_textcontent_safe",
            "PASS" if xss_pass else "FAIL",
            f"no_innerHTML={no_inner} probe={xss_ok}",
            "mocked",
        )

        browser.close()

    mandatory = [c for c in checks if not c["skipped"]]
    skipped = [c for c in checks if c["skipped"]]
    failed = [c for c in mandatory if c["status"] == "FAIL"]
    passed = [c for c in mandatory if c["status"] == "PASS"]

    by_bucket: dict[str, dict[str, int]] = {}
    for c in checks:
        b = c["bucket"]
        by_bucket.setdefault(b, {"PASS": 0, "FAIL": 0, "SKIPPED": 0, "NOT_RUN": 0})
        by_bucket[b][c["status"]] = by_bucket[b].get(c["status"], 0) + 1

    report = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "base": BASE,
        "credentials_present": bool(caps.get("nebius_api_key_present")),
        "checks": checks,
        "screenshots": screens,
        "summary": {
            "mandatory_pass": len(passed),
            "mandatory_fail": len(failed),
            "skipped_or_not_run": len(skipped),
            "total": len(checks),
            "by_bucket": by_bucket,
        },
        "passed": len(failed) == 0,
        # Backward-compat fields (do NOT treat skipped as pass)
        "pass_count": len(passed),
        "fail_count": len(failed),
        "skip_count": len(skipped),
        "total": len(checks),
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "pass_count": report["pass_count"],
                "fail_count": report["fail_count"],
                "skip_count": report["skip_count"],
                "total": report["total"],
                "by_bucket": by_bucket,
                "out": str(REPORT),
            },
            indent=2,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
