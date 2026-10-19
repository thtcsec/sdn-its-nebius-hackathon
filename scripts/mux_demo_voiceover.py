#!/usr/bin/env python3
"""Generate English voiceover + mux into JunctionTrace demo MP4 (with audio).

Explicitly names NVIDIA Nemotron and Nebius Token Factory.
Uses Windows SAPI (PowerShell) when available, else documents blocker.
Removes prior silent (-an) conversion path for the final artifact.

Outputs:
  artifacts/demo_video/junctiontrace_voiceover.wav
  artifacts/demo_video/junctiontrace_judge_demo_with_audio.mp4
  artifacts/demo_video/media_verify.json
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "demo_video"
VIDEO_IN = OUT / "junctiontrace_judge_demo.mp4"
WEBM_IN = OUT / "junctiontrace_judge_demo.webm"
WAV = OUT / "junctiontrace_voiceover.wav"
VIDEO_OUT = OUT / "junctiontrace_judge_demo_with_audio.mp4"
VERIFY = OUT / "media_verify.json"

# ~150–170s paced read (SSML breaks via pauses in Speak)
VOICEOVER_SCRIPT = """
A traffic surge is not always a cyber attack.
JunctionTrace helps operators investigate physical context before disruptive containment.
This product uses NVIDIA Nemotron through the Nebius Token Factory.
First, a legitimate congestion scenario: the offline planner and rule-only baseline avoid unnecessary disruption.
Next, a real multi-step investigation with NVIDIA Nemotron on Nebius Token Factory:
evidence tools retrieve telemetry and synthetic camera metadata, then the model recommends an action.
The authoritative policy gate remains in charge.
Limitations: camera fields are synthetic metadata, OpenFlow stays mock, and operation is advisory only.
Offline planners can be competitive on some synthetic tests —
Nemotron adds tool-mediated investigation and a clearly labeled live conclude path via Nebius Token Factory.
"""


def _ffprobe_streams(path: Path) -> dict:
    if not shutil.which("ffprobe"):
        return {"error": "ffprobe_missing"}
    raw = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=index,codec_type,codec_name",
            "-of",
            "json",
            str(path),
        ],
        text=True,
    )
    return json.loads(raw)


def _synthesize_wav(wav: Path) -> bool:
    """Windows SAPI TTS → WAV."""
    if sys.platform != "win32":
        return False
    wav.parent.mkdir(parents=True, exist_ok=True)
    # Escape for PowerShell here-string
    text = VOICEOVER_SCRIPT.strip().replace("'", "''")
    ps = f"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Rate = -1
$s.SetOutputToWaveFile('{wav.as_posix().replace('/', '\\')}')
$s.Speak(@'
{VOICEOVER_SCRIPT.strip()}
'@)
$s.Dispose()
"""
    try:
        subprocess.check_call(
            ["powershell", "-NoProfile", "-Command", ps],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return wav.is_file() and wav.stat().st_size > 1000
    except Exception:
        return False


def _ensure_silent_video() -> Path | None:
    if VIDEO_IN.is_file():
        return VIDEO_IN
    if WEBM_IN.is_file() and shutil.which("ffmpeg"):
        VIDEO_IN.parent.mkdir(parents=True, exist_ok=True)
        subprocess.check_call(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(WEBM_IN),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-an",
                "-movflags",
                "+faststart",
                str(VIDEO_IN),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return VIDEO_IN if VIDEO_IN.is_file() else None
    return None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    video = _ensure_silent_video()
    if video is None:
        print("ERROR: missing demo video; run scripts/record_junctiontrace_demo.py first", file=sys.stderr)
        return 2
    if not shutil.which("ffmpeg"):
        print("ERROR: ffmpeg required", file=sys.stderr)
        return 2

    if not _synthesize_wav(WAV):
        report = {
            "ok": False,
            "blocker": "Could not synthesize English voiceover via Windows SAPI.",
            "script_path": "scripts/mux_demo_voiceover.py",
            "voiceover_text": VOICEOVER_SCRIPT.strip(),
            "instruction": "Record VOICEOVER_SCRIPT as WAV naming NVIDIA Nemotron and Nebius Token Factory, then re-run this script.",
        }
        VERIFY.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    # Keep full video length (<180s); pad VO with silence after speech ends (no -shortest).
    vinfo = _ffprobe_streams(video)
    vdur = float((vinfo.get("format") or {}).get("duration") or 0)
    if vdur <= 0 or vdur >= 180:
        print(f"ERROR: source video duration {vdur}s not in (0,180)", file=sys.stderr)
        return 1
    subprocess.check_call(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-i",
            str(WAV),
            "-filter_complex",
            f"[1:a]apad=whole_dur={vdur:.3f},atrim=0:{vdur:.3f},asetpts=N/SR/TB[a]",
            "-map",
            "0:v",
            "-map",
            "[a]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-t",
            f"{vdur:.3f}",
            "-movflags",
            "+faststart",
            str(VIDEO_OUT),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    info = _ffprobe_streams(VIDEO_OUT)
    streams = info.get("streams") or []
    types = {s.get("codec_type") for s in streams}
    duration = float((info.get("format") or {}).get("duration") or 0)
    has_audio = "audio" in types
    has_video = "video" in types
    ok = has_audio and has_video and 0 < duration < 180
    report = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "ok": ok,
        "mp4": str(VIDEO_OUT),
        "wav": str(WAV),
        "duration_s": duration,
        "has_audio": has_audio,
        "has_video": has_video,
        "streams": streams,
        "names_nemotron": "NVIDIA Nemotron" in VOICEOVER_SCRIPT,
        "names_nebius_token_factory": "Nebius Token Factory" in VOICEOVER_SCRIPT,
        "note": "Final competition media with English VO. Do not upload without owner approval.",
    }
    VERIFY.write_text(json.dumps(report, indent=2), encoding="utf-8")
    # Also update silent conversion path documentation in record script consumers
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
