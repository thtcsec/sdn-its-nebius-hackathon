#!/usr/bin/env python
"""Record a smoother IEDE console demo with smaller, metric-focused English subtitles."""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "demo_video"
RAW_DIR = OUT / "raw"
BASE = "http://127.0.0.1:8080"

# Cue list filled after recording with measured beat times + metric snapshots
BEATS: list[dict] = []


def wait_api(timeout_s: float = 60.0) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            if requests.get(BASE + "/api/v1/status", timeout=3).status_code == 200:
                return
        except Exception:
            pass
        time.sleep(1)
    raise SystemExit("API not on :8080")


def srt_ts(seconds: float) -> str:
    ms = max(0, int(round(seconds * 1000)))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(path: Path, cues: list[tuple[float, float, str]]) -> None:
    lines: list[str] = []
    for i, (a, b, text) in enumerate(cues, 1):
        # allow multi-line subtitle with |
        body = text.replace(" | ", "\n")
        lines += [str(i), f"{srt_ts(a)} --> {srt_ts(b)}", body, ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def snap_metrics() -> dict:
    st = requests.get(BASE + "/api/v1/status", timeout=20).json()
    cam = requests.get(BASE + "/api/v1/camera", timeout=30).json()
    rules = requests.get(BASE + "/api/v1/active_rules", timeout=20).json()
    settings = requests.get(BASE + "/api/v1/settings", timeout=20).json()
    rt = settings.get("runtime") or {}
    agg = cam.get("aggregate") or {}
    return {
        "model_loaded": st.get("model_loaded"),
        "of_backend": st.get("of_backend"),
        "network_evidence": st.get("network_evidence"),
        "lab_mode": rt.get("lab_mode", st.get("lab_mode")),
        "scenario_override": rt.get("scenario_override", st.get("scenario_override")),
        "tau": rt.get("tau"),
        "live_rtsp": agg.get("live_rtsp"),
        "tracks": agg.get("visible_vehicle_tracks"),
        "phys": agg.get("physical_label"),
        "source": agg.get("source"),
        "rules": rules.get("count"),
        "actuation_note": (rules.get("actuation_note") or "")[:48],
    }


def fmt_tau(v) -> str:
    try:
        return f"{float(v):.1f}"
    except Exception:
        return "?"


def record() -> tuple[Path, float, list[tuple[float, float, str]]]:
    OUT.mkdir(parents=True, exist_ok=True)
    if RAW_DIR.exists():
        shutil.rmtree(RAW_DIR)
    RAW_DIR.mkdir(parents=True)

    requests.post(
        BASE + "/api/v1/settings",
        json={"lab_mode": False, "scenario_override": True},
        timeout=30,
    )
    requests.post(BASE + "/api/v1/camera/scenario", json={"scenario": "idle"}, timeout=30)

    cues: list[tuple[float, float, str]] = []
    marks: list[tuple[float, str, dict]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir=str(RAW_DIR),
            record_video_size={"width": 1440, "height": 900},
        )
        page = context.new_page()
        t0 = time.time()

        def elapsed() -> float:
            return time.time() - t0

        def beat(title: str, hold: float = 2.5) -> None:
            m = snap_metrics()
            marks.append((elapsed(), title, m))
            print(f"  [{elapsed():5.1f}s] {title} tau={m.get('tau')} tracks={m.get('tracks')} phys={m.get('phys')}")
            time.sleep(hold)

        def close_settings() -> None:
            page.evaluate(
                """() => {
                  const d=document.getElementById('settings-drawer');
                  if(d){d.classList.remove('open'); d.setAttribute('aria-hidden','true');}
                  const b=document.getElementById('settings-backdrop');
                  if(b) b.classList.remove('open');
                }"""
            )

        page.goto(BASE, wait_until="networkidle", timeout=90000)
        time.sleep(2.0)
        close_settings()
        page.evaluate("window.scrollTo({top:0, behavior:'smooth'})")
        beat("overview", 4.0)

        # Highlight evidence strip area
        page.evaluate("window.scrollTo({top:0, behavior:'smooth'})")
        beat("evidence_strip", 4.5)

        # Settings
        if page.locator("#btn-settings").count():
            page.click("#btn-settings")
            time.sleep(1.2)
            for sel, want in (("#set-lab", False), ("#set-scenario-override", True)):
                loc = page.locator(sel)
                if loc.count():
                    if loc.is_checked() != want:
                        loc.click()
                        time.sleep(0.4)
            beat("settings", 4.0)
            close_settings()
            time.sleep(0.8)

        # Live cameras — slow scroll
        page.evaluate(
            """() => {
              const el=document.getElementById('fusion-row');
              if(el) el.scrollIntoView({behavior:'smooth', block:'start'});
            }"""
        )
        time.sleep(1.5)
        live = page.locator('button[data-cam-scen="idle"]')
        if live.count():
            live.first.click()
            time.sleep(2.0)
        # wait for detector aggregate
        for _ in range(6):
            m = snap_metrics()
            if m.get("source") == "detector_tracker_v1" or int(m.get("live_rtsp") or 0) > 0:
                break
            time.sleep(1.0)
        beat("live_cameras", 6.0)

        # Rush preserve path
        rush = page.locator('button[data-cam-scen="rush"]')
        if rush.count():
            rush.first.click()
            time.sleep(1.0)
        requests.post(BASE + "/api/v1/camera/scenario", json={"scenario": "rush"}, timeout=20)
        fus = requests.post(
            BASE + "/api/v1/camera/fusion_preview",
            json={"network_prediction": "DDoS_PacketIn_Flood", "source_dominance": 0.30},
            timeout=20,
        ).json()
        requests.post(
            BASE + "/api/v1/anomaly_alert",
            json={
                "alert_id": "DEMO-RUSH",
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
            timeout=20,
        )
        page.evaluate("window.scrollTo({top:0, behavior:'smooth'})")
        time.sleep(0.8)
        ddos = page.locator('button.scenario-btn.ddos[onclick*="DDoS"]')
        if ddos.count():
            ddos.first.click()
        time.sleep(1.5)
        page.evaluate(
            """() => {
              const el=document.getElementById('panel-fusion')||document.getElementById('fusion-row');
              if(el) el.scrollIntoView({behavior:'smooth', block:'center'});
            }"""
        )
        time.sleep(1.5)
        marks.append(
            (
                elapsed(),
                "fusion_preserve",
                {
                    **snap_metrics(),
                    "fusion_action": fus.get("recommended_action"),
                    "fusion_phys": fus.get("physical_context"),
                    "dominance": 0.30,
                },
            )
        )
        print(f"  [{elapsed():5.1f}s] fusion_preserve action={fus.get('recommended_action')}")
        time.sleep(6.5)

        # Containment path
        requests.post(
            BASE + "/api/v1/camera/scenario",
            json={"scenario": "attack_physical_stable"},
            timeout=20,
        )
        fus2 = requests.post(
            BASE + "/api/v1/camera/fusion_preview",
            json={"network_prediction": "DDoS_PacketIn_Flood", "source_dominance": 0.85},
            timeout=20,
        ).json()
        requests.post(
            BASE + "/api/v1/anomaly_alert",
            json={
                "alert_id": "DEMO-DROP",
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
            timeout=20,
        )
        page.evaluate("window.scrollTo({top:0, behavior:'smooth'})")
        time.sleep(0.8)
        if ddos.count():
            ddos.first.click()
        time.sleep(1.5)
        page.evaluate(
            """() => {
              const h=[...document.querySelectorAll('h2')]
                .find(x=>/Reconstruction error|Intended mitigation/i.test(x.textContent||''));
              if(h) h.scrollIntoView({behavior:'smooth', block:'start'});
            }"""
        )
        time.sleep(1.2)
        m2 = snap_metrics()
        marks.append(
            (
                elapsed(),
                "containment",
                {
                    **m2,
                    "fusion_action": fus2.get("recommended_action"),
                    "fusion_phys": fus2.get("physical_context"),
                    "dominance": 0.85,
                },
            )
        )
        print(f"  [{elapsed():5.1f}s] containment action={fus2.get('recommended_action')} rules={m2.get('rules')}")
        time.sleep(7.0)

        page.evaluate("window.scrollTo({top:0, behavior:'smooth'})")
        beat("closing", 4.0)

        duration = elapsed()
        page.close()
        context.close()
        browser.close()

    # Build cues from marks — smaller text, metrics explicit
    def cue_for(i: int, start: float, end: float, kind: str, m: dict) -> tuple[float, float, str]:
        tau = fmt_tau(m.get("tau"))
        tracks = m.get("tracks")
        phys = m.get("phys")
        live = m.get("live_rtsp")
        ofb = m.get("of_backend")
        ne = m.get("network_evidence")
        act = m.get("fusion_action")
        dom = m.get("dominance")
        rules = m.get("rules")
        if kind == "overview":
            text = (
                f"Console online — research prototype demo | "
                f"MODEL loaded · OF·{ofb} · NET evidence={ne}"
            )
        elif kind == "evidence_strip":
            text = (
                f"Read the evidence strip first | "
                f"τ≈{tau} · PRED may show flood while GT stays honest in lab"
            )
        elif kind == "settings":
            text = (
                f"Settings: Lab mode={m.get('lab_mode')} · override={m.get('scenario_override')} | "
                f"Needed so inject buttons drive the demo path"
            )
        elif kind == "live_cameras":
            text = (
                f"Live RTSP cameras · live_rtsp={live} · tracks≈{tracks} · phys={phys} | "
                f"source={m.get('source')} — context only, not veh/h census"
            )
        elif kind == "fusion_preserve":
            text = (
                f"NOW: rush physics + flood alert · dominance={dom} | "
                f"Fusion → {act} (phys={m.get('fusion_phys')}) — avoid hard block"
            )
        elif kind == "containment":
            text = (
                f"NOW: stable cam + high dominance={dom} | "
                f"Fusion → {act} · in-memory rules≈{rules} · OF·{ofb} (not switch-verified)"
            )
        else:
            text = (
                f"Summary: detect → fuse → temporary contain/rollback | "
                f"Claim only what the evidence grade allows"
            )
        return (start, end, text)

    # Convert marks to non-overlapping windows
    for i, (t, kind, m) in enumerate(marks):
        start = max(0.2, t - 0.3)
        end = marks[i + 1][0] - 0.15 if i + 1 < len(marks) else duration - 0.2
        if end <= start + 1.2:
            end = start + 3.0
        cues.append(cue_for(i, start, min(end, duration - 0.05), kind, m))

    videos = list(RAW_DIR.glob("*.webm"))
    if not videos:
        raise SystemExit("no webm")
    raw = OUT / "iede_console_demo_raw.webm"
    shutil.copyfile(videos[0], raw)
    return raw, duration, cues


def burn(raw: Path, srt: Path, mp4: Path) -> None:
    # Smaller font (14), bottom margin, semi-transparent box
    srt_esc = srt.resolve().as_posix().replace(":", "\\:")
    vf = (
        f"subtitles='{srt_esc}':force_style='"
        "FontName=Arial,FontSize=13,Bold=0,"
        "PrimaryColour=&H00FFFFFF&,OutlineColour=&H80000000&,BackColour=&H80000000&,"
        "BorderStyle=4,Outline=0,Shadow=0,MarginL=40,MarginR=40,MarginV=22,"
        "Alignment=2'"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(raw),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-an",
        str(mp4),
    ]
    print("[*] ffmpeg burn (small captions, CRF18, 30fps)...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1200:])
        raise SystemExit("ffmpeg burn failed")
    print(f"[+] {mp4} ({mp4.stat().st_size // 1024} KB)")


def main() -> None:
    wait_api()
    raw, duration, cues = record()
    srt = OUT / "iede_console_demo_en.srt"
    write_srt(srt, cues)
    print(f"[+] duration≈{duration:.1f}s cues={len(cues)}")
    for a, b, t in cues:
        print(f"    {a:5.1f}-{b:5.1f}: {t[:90]}")
    mp4 = OUT / "iede_console_demo_en.mp4"
    burn(raw, srt, mp4)
    print("\nDONE")
    print(" ", mp4)


if __name__ == "__main__":
    main()
