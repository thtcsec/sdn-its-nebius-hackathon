#!/usr/bin/env python3
"""Record a genuine headed JunctionTrace walkthrough (real UI, real clicks).

Captures:
  - ffmpeg gdigrab of the visible Chrome window (OS cursor drawn)
  - Playwright viewport video as a backup
  - timestamped event log for hard-cut editing

Does not overwrite junctiontrace_judge_demo*.mp4.
Does not fabricate inference results.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "demo_video"
BASE = os.environ.get("JT_BASE_URL", "http://127.0.0.1:8080")

user32 = ctypes.windll.user32
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def _caps_safe(raw: dict) -> dict:
    return {
        "nebius_api_key_present": bool(raw.get("nebius_api_key_present")),
        "nebius_model": raw.get("nebius_model"),
        "of_backend_default": raw.get("of_backend_default"),
        "api_token_required": bool(raw.get("api_token_required")),
    }


def move_cursor(x: int, y: int) -> None:
    user32.SetCursorPos(int(x), int(y))


def smooth_move(x0: int, y0: int, x1: int, y1: int, steps: int = 14) -> None:
    for i in range(1, steps + 1):
        t = i / steps
        move_cursor(int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t))
        time.sleep(0.018)


def left_click() -> None:
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.04)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def window_metrics(page) -> dict:
    return page.evaluate(
        """() => ({
          sx: window.screenX,
          sy: window.screenY,
          ox: window.outerWidth,
          oy: window.outerHeight,
          ix: window.innerWidth,
          iy: window.innerHeight,
          dpr: window.devicePixelRatio || 1
        })"""
    )


def screen_xy(page, box: dict) -> tuple[int, int]:
    m = window_metrics(page)
    # Typical Chrome: title/tab strip sits above the inner viewport.
    chrome_x = max(0, int(round((m["ox"] - m["ix"]) / 2)))
    chrome_y = max(0, int(round(m["oy"] - m["iy"] - chrome_x)))
    x = int(m["sx"] + chrome_x + box["x"] + box["width"] / 2)
    y = int(m["sy"] + chrome_y + box["y"] + box["height"] / 2)
    return x, y


class Recorder:
    def __init__(self, raw_dir: Path, page):
        self.raw_dir = raw_dir
        self.page = page
        self.t0 = time.perf_counter()
        self.events: list[dict] = []
        self._last_xy = (960, 540)

    def t(self) -> float:
        return round(time.perf_counter() - self.t0, 3)

    def mark(self, name: str, **extra) -> None:
        row = {"t": self.t(), "name": name}
        row.update(extra)
        self.events.append(row)
        print(f"[{row['t']:7.2f}] {name}", extra if extra else "", flush=True)

    def click(self, selector: str, name: str, timeout: float = 15000) -> None:
        loc = self.page.locator(selector).first
        loc.wait_for(state="visible", timeout=timeout)
        loc.scroll_into_view_if_needed()
        time.sleep(0.25)
        box = loc.bounding_box()
        if not box:
            raise RuntimeError(f"no bounding box for {selector}")
        x, y = screen_xy(self.page, box)
        smooth_move(self._last_xy[0], self._last_xy[1], x, y)
        self._last_xy = (x, y)
        time.sleep(0.12)
        self.mark(name, selector=selector, x=x, y=y)
        # OS cursor is visible to gdigrab; Playwright delivers exactly one click.
        loc.click(timeout=4000)

    def dwell(self, seconds: float, name: str) -> None:
        self.mark(f"dwell_start_{name}", seconds=seconds)
        time.sleep(seconds)
        self.mark(f"dwell_end_{name}")


def start_ffmpeg(out_mp4: Path) -> subprocess.Popen:
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "gdigrab",
        "-framerate",
        "30",
        "-offset_x",
        "0",
        "-offset_y",
        "0",
        "-video_size",
        "1920x1080",
        "-draw_mouse",
        "1",
        "-i",
        "desktop",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        str(out_mp4),
    ]
    log = out_mp4.with_suffix(".ffmpeg.log")
    lf = open(log, "w", encoding="utf-8")
    return subprocess.Popen(cmd, stdout=lf, stderr=lf, stdin=subprocess.PIPE)


def stop_ffmpeg(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        if proc.stdin:
            proc.stdin.write(b"q")
            proc.stdin.flush()
    except Exception:
        pass
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()


def foreground_chrome() -> None:
    """Bring a JunctionTrace Chrome window to 0,0 1920x1080."""
    EnumWindows = user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    GetWindowTextW = user32.GetWindowTextW
    IsWindowVisible = user32.IsWindowVisible
    found = []

    def _cb(hwnd, _):
        if IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(512)
            GetWindowTextW(hwnd, buf, 512)
            title = buf.value or ""
            if "JunctionTrace" in title:
                found.append(hwnd)
        return True

    EnumWindows(EnumWindowsProc(_cb), 0)
    if not found:
        return
    hwnd = found[0]
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    user32.MoveWindow(hwnd, 0, 0, 1920, 1080, True)
    time.sleep(0.3)


def extract_result_fields(page) -> dict:
    text = page.locator("#result-body").inner_text()
    return {
        "excerpt": text[:1200],
        "has_real_api": "real_api" in text or "LIVE Nebius" in text,
        "has_planner": "deterministic planner" in text.lower() or "deterministic_planner" in text,
        "has_nemotron_conclude": "nemotron_conclude" in text,
        "has_fallback": "deterministic_fallback" in text,
        "has_observe": "observe" in text.lower(),
        "has_rate_limit": "rate_limit" in text,
        "has_gate": "gate" in text.lower(),
    }


def run(dry_run: bool) -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed", file=sys.stderr)
        return 2

    if not shutil.which("ffmpeg"):
        print("ERROR: ffmpeg required for gdigrab capture", file=sys.stderr)
        return 2

    caps = _caps_safe(_get("/api/v1/hackathon/capabilities"))
    print("CAPABILITIES", json.dumps(caps), flush=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_dir = OUT / f"real_app_raw_{stamp}"
    raw_dir.mkdir(parents=True, exist_ok=True)
    grab_path = raw_dir / "gdigrab_source.mp4"
    proof_path = raw_dir / "capture_proof.json"

    events_meta: dict = {
        "ts_utc": _now(),
        "base": BASE,
        "capabilities": caps,
        "screen": "1920x1080",
        "fps": 30,
        "voice_plan": "Microsoft David Desktop / SAPI / single male en-US",
        "dry_run": dry_run,
        "raw_dir": str(raw_dir),
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=False,
            args=[
                "--window-position=0,0",
                "--window-size=1920,1080",
                "--disable-infobars",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-features=Translate,MediaRouter",
                "--autoplay-policy=no-user-gesture-required",
            ],
            ignore_default_args=["--enable-automation"],
        )
        pw_dir = raw_dir / "playwright"
        pw_dir.mkdir(parents=True, exist_ok=True)
        ctx_kwargs = {
            "viewport": {"width": 1920, "height": 1080},
            "device_scale_factor": 1,
        }
        try:
            context = browser.new_context(
                **ctx_kwargs,
                record_video_dir=str(pw_dir),
                record_video_size={"width": 1920, "height": 1080},
            )
        except Exception as exc:
            print(f"NOTE: Playwright video disabled ({exc})", flush=True)
            context = browser.new_context(**ctx_kwargs)
        page = context.new_page()
        rec = Recorder(raw_dir, page)

        page.goto(f"{BASE}/", wait_until="domcontentloaded")
        page.locator("h1").first.wait_for()
        page.locator("#cap-mode").wait_for()
        time.sleep(0.6)
        foreground_chrome()
        page.bring_to_front()
        time.sleep(0.4)

        ff = start_ffmpeg(grab_path)
        rec.t0 = time.perf_counter()
        rec.mark("ffmpeg_started", pid=ff.pid)
        rec.mark("page_loaded", title=page.title())

        # —— Scene A: launch / identity (product name + purpose on screen) ——
        rec.dwell(8.0, "hero_identity")
        page.locator("#scenario-grid").scroll_into_view_if_needed()
        rec.mark("scroll_scenarios")
        rec.dwell(2.0, "scenarios_visible")

        # —— Scene B: offline investigation ——
        rec.click("#mode-offline", "click_mode_offline")
        rec.click('.scenario-card[data-id="scenario_rush_vs_attack"]', "click_scenario_a")
        rec.dwell(1.4, "scenario_a_selected")
        rec.click("#btn-investigate", "click_investigate_offline")
        page.locator("#loading-state").wait_for(state="visible", timeout=8000)
        rec.mark("offline_loading_visible")
        page.wait_for_function(
            """() => {
              const t = document.querySelector('#result-body')?.innerText || '';
              return t.includes('deterministic planner') || t.includes('preserve_rush_hour')
                || t.includes('error') || t.includes('fail-closed');
            }""",
            timeout=30000,
        )
        rec.mark("offline_result_visible")
        rec.dwell(2.0, "offline_badges")
        page.locator("#timeline").scroll_into_view_if_needed()
        rec.mark("scroll_offline_timeline")
        rec.dwell(3.2, "offline_tools")
        page.locator("#d5").scroll_into_view_if_needed()
        rec.dwell(2.0, "offline_recommendation")
        page.locator("#result-body").scroll_into_view_if_needed()
        rec.dwell(3.5, "offline_result_board")
        events_meta["offline"] = extract_result_fields(page)

        if dry_run:
            rec.mark("dry_run_stop")
        else:
            # —— Scene C: real Nebius / Nemotron ——
            page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
            rec.dwell(1.0, "scroll_top_for_real")
            rec.click("#mode-real", "click_mode_real")
            rec.dwell(1.6, "mode_real_hint")
            rec.click('.scenario-card[data-id="scenario_loft_stable"]', "click_scenario_b")
            rec.dwell(1.4, "scenario_b_selected")
            rec.click("#btn-investigate", "click_investigate_real")
            page.locator("#loading-state").wait_for(state="visible", timeout=8000)
            rec.mark("real_loading_visible")
            deadline = time.time() + 180
            while time.time() < deadline:
                foreground_chrome()
                ready = page.evaluate(
                    """() => {
                      const t = document.querySelector('#result-body')?.innerText || '';
                      return t.includes('real_api') || t.includes('LIVE Nebius')
                        || t.includes('blocked') || t.includes('error')
                        || t.includes('budget') || t.includes('deterministic')
                        || t.includes('fail-closed') || t.includes('validation');
                    }"""
                )
                if ready:
                    break
                time.sleep(0.45)
            else:
                rec.mark("real_wait_timeout")
            rec.mark("real_result_visible")
            rec.dwell(2.2, "real_badges")
            page.locator("#d3").scroll_into_view_if_needed()
            rec.mark("scroll_real_tools")
            rec.dwell(4.0, "real_tool_selection")
            page.locator("#d4").scroll_into_view_if_needed()
            rec.dwell(3.2, "real_tool_results")
            page.locator("#d5").scroll_into_view_if_needed()
            rec.dwell(3.5, "real_conclude")
            page.locator("#d6").scroll_into_view_if_needed()
            rec.dwell(2.5, "real_gate")
            page.locator("#result-body").scroll_into_view_if_needed()
            rec.dwell(8.0, "real_operator_board")
            events_meta["real"] = extract_result_fields(page)

            # —— Scene D: limitations on the same product screen ——
            rec.dwell(9.0, "limitations_on_result")
            rec.mark("end_on_product")

        rec.mark("capture_stopping")
        time.sleep(0.4)
        stop_ffmpeg(ff)
        rec.mark("ffmpeg_stopped")

        context.close()
        browser.close()

    videos = list((raw_dir / "playwright").glob("*.webm"))
    events_meta["events"] = rec.events
    events_meta["gdigrab"] = str(grab_path) if grab_path.is_file() else None
    events_meta["gdigrab_bytes"] = grab_path.stat().st_size if grab_path.is_file() else 0
    events_meta["playwright_webm"] = str(videos[0]) if videos else None
    events_meta["duration_wall_s"] = rec.events[-1]["t"] if rec.events else None
    proof_path.write_text(json.dumps(events_meta, indent=2), encoding="utf-8")
    print(json.dumps({"raw_dir": str(raw_dir), "gdigrab": events_meta["gdigrab"], "webm": events_meta["playwright_webm"], "events": len(rec.events)}, indent=2))
    if not grab_path.is_file() or grab_path.stat().st_size < 50_000:
        print("WARNING: gdigrab file missing or tiny — editor should fall back to Playwright webm", file=sys.stderr)
        return 0 if videos else 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
