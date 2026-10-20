#!/usr/bin/env python3
"""Record a competition-quality JunctionTrace walkthrough via Playwright.

Target duration ~150–180s with deliberate dwells (narration pacing).
Produces WebM + MP4 (if ffmpeg) under artifacts/demo_video/.
Records the actual running UI — does not fabricate success.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "demo_video"
BASE = os.environ.get("JT_BASE_URL", "http://127.0.0.1:8080")
JUDGE_TOKEN = (os.environ.get("SDN_API_TOKEN") or os.environ.get("JT_JUDGE_TOKEN") or "").strip()


def dwell(seconds: float) -> None:
    time.sleep(seconds)


def _duration_seconds(path: Path) -> float | None:
    if not shutil.which("ffprobe"):
        return None
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            text=True,
        ).strip()
        return float(out)
    except Exception:
        return None


def _to_mp4(webm: Path, mp4: Path) -> bool:
    """Video-only intermediate. Final competition file must use mux_demo_voiceover.py (with audio)."""
    if not shutil.which("ffmpeg"):
        return False
    try:
        # Keep any source audio if present; do NOT force -an.
        subprocess.check_call(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(webm),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                str(mp4),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return mp4.is_file()
    except Exception:
        # Playwright webm often has no audio stream — fall back to video-only encode.
        try:
            subprocess.check_call(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(webm),
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                    str(mp4),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return mp4.is_file()
        except Exception:
            return False


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed", file=sys.stderr)
        return 2

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_dir = OUT_DIR / f"raw_{stamp}"
    raw_dir.mkdir(parents=True, exist_ok=True)

    meta: dict = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "base": BASE,
        "segments": [],
        "note": "Screen capture of live JunctionTrace UI. Do not upload without owner approval.",
        "voiceover_cues": [
            "0:00 Pain point: surge labels can destroy legitimate mobility traffic",
            "0:15 JunctionTrace homepage — NVIDIA Nemotron via Nebius Token Factory",
            "0:40 Scenario A offline congestion vs rule-only",
            "1:10 Scenario B real Nemotron tools + evidence + gate",
            "2:10 Limitations: synthetic camera, mock OF, advisory (product footer only)",,
        ],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir=str(raw_dir),
            record_video_size={"width": 1440, "height": 900},
        )
        page = context.new_page()

        # —— 0:00–0:35 landing / pain point ——
        page.goto(f"{BASE}/", wait_until="networkidle")
        page.locator("h1").first.wait_for()
        dwell(12)
        page.locator("#scenario-grid").scroll_into_view_if_needed()
        dwell(8)
        page.locator(".diff-box").first.scroll_into_view_if_needed()
        dwell(8)
        page.evaluate("window.scrollTo(0,0)")
        dwell(6)
        meta["segments"].append("landing_pain_point")

        # —— 0:35–1:15 Scenario A offline ——
        page.locator("#mode-offline").click()
        page.locator('.scenario-card[data-id="scenario_rush_vs_attack"]').click()
        dwell(3)
        page.locator("#btn-investigate").click()
        page.wait_for_selector(".badge", timeout=90000)
        dwell(4)
        page.locator("#timeline").scroll_into_view_if_needed()
        dwell(8)
        page.locator("#result-body").scroll_into_view_if_needed()
        dwell(14)
        meta["segments"].append("scenario_a_offline_congestion")

        # —— 1:15–2:20 Real Nemotron ——
        caps = page.evaluate("async () => (await fetch('/api/v1/hackathon/capabilities')).json()")
        meta["nebius_api_key_present"] = bool(caps.get("nebius_api_key_present"))
        if JUDGE_TOKEN:
            page.evaluate(
                """(tok) => { const el = document.getElementById('judge-token'); if (el) el.value = tok; }""",
                JUDGE_TOKEN,
            )
        page.evaluate("window.scrollTo(0,0)")
        dwell(2)
        if caps.get("nebius_api_key_present"):
            page.locator("#mode-real").click()
            dwell(2)
            page.locator('.scenario-card[data-id="scenario_loft_stable"]').click()
            dwell(2)
            page.locator("#btn-investigate").click()
            page.wait_for_function(
                """() => {
                  const t = document.querySelector('#result-body')?.innerText || '';
                  return t.includes('real_api') || t.includes('LIVE') || t.includes('blocked')
                    || t.includes('error') || t.includes('budget') || t.includes('deterministic');
                }""",
                timeout=120000,
            )
            dwell(4)
            page.locator("#d3").scroll_into_view_if_needed()
            dwell(8)
            page.locator("#d4").scroll_into_view_if_needed()
            dwell(6)
            page.locator("#d5").scroll_into_view_if_needed()
            dwell(6)
            page.locator("#result-body").scroll_into_view_if_needed()
            dwell(16)
            body = page.locator("#result-body").inner_text()
            meta["segments"].append("scenario_b_real_nemotron")
            meta["real_body_excerpt"] = body[:500]
        else:
            page.locator("#mode-real").click()
            dwell(12)
            meta["segments"].append("scenario_b_skipped_no_credentials")

        # Limitations on the product page only. Do not record /research:
        # that console still shows inherited "TSINGHUA IEDE" chrome.
        page.goto(f"{BASE}/", wait_until="networkidle")
        page.locator(".footer-note").scroll_into_view_if_needed()
        dwell(14)
        meta["segments"].append("limitations_footer")

        context.close()
        browser.close()

    videos = list(raw_dir.glob("*.webm"))
    if not videos:
        print("ERROR: no webm recorded", file=sys.stderr)
        return 1
    webm = videos[0]
    final_webm = OUT_DIR / "junctiontrace_judge_demo.webm"
    shutil.copy2(webm, final_webm)
    mp4 = OUT_DIR / "junctiontrace_judge_demo.mp4"
    converted = _to_mp4(final_webm, mp4)
    dur = _duration_seconds(mp4 if converted else final_webm)
    meta["webm"] = str(final_webm)
    meta["mp4"] = str(mp4) if converted else None
    meta["duration_s"] = dur
    meta["converted_mp4"] = converted
    meta_path = OUT_DIR / "junctiontrace_judge_demo_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps({k: meta[k] for k in ("webm", "mp4", "duration_s", "converted_mp4", "segments", "nebius_api_key_present")}, indent=2))
    if dur is None:
        print("WARNING: could not measure duration", file=sys.stderr)
        return 0
    if dur < 150:
        print(f"BLOCKER: duration {dur:.1f}s < 150s target", file=sys.stderr)
        return 1
    if dur > 200:
        print(f"NOTE: duration {dur:.1f}s long — trim in editor to ≤180s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
