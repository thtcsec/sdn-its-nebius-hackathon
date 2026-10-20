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


# Judge pitch pack: drop dead landing/footer/spinner, keep real UI, timed English VO.
# Source timestamps refer to junctiontrace_judge_demo_with_audio.mp4 (155.84s trimmed file).
PITCH_VIDEO_CLIPS = [
    (1.0, 15.0),    # hero
    (44.0, 66.0),   # offline tools + preserve_rush_hour
    (70.0, 88.0),   # Scenario B + Real Nebius wait (honest latency, not full 28s)
    (102.0, 142.0), # live Nemotron tools, observe vs rate_limit, gate PASS
]
PITCH_CUES = [
    (
        0.0,
        "A traffic surge is not always a cyber attack. "
        "JunctionTrace investigates physical context before containment. "
        "This product uses NVIDIA Nemotron through the Nebius Token Factory.",
    ),
    (
        14.0,
        "First, legitimate congestion. Tools retrieve telemetry and synthetic camera metadata. "
        "The offline planner and the rule baseline both preserve rush hour. "
        "The policy gate stays in charge. This path is not live Nemotron.",
    ),
    (
        36.0,
        "Now a quiet-zone anomaly. NVIDIA Nemotron on Nebius Token Factory selects evidence tools. "
        "Live inference takes about twenty seconds. That is advisory latency, not real-time control.",
    ),
    (
        54.0,
        "Nemotron called camera metadata, network telemetry, and a temporal compare. "
        "Physical activity is low and stable, so the model concludes observe. "
        "Rule-only would rate-limit. The gate passes. OpenFlow is mock. Camera fields are synthetic metadata.",
    ),
    (
        76.0,
        "Operator impact: physical context changed the decision from rate-limit to observe. "
        "No live switch containment is performed.",
    ),
]


def _sapi_wav(text: str, wav: Path) -> bool:
    if sys.platform != "win32":
        return False
    wav.parent.mkdir(parents=True, exist_ok=True)
    body = text.strip().replace("'", "''")
    ps = f"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Rate = -1
$s.SetOutputToWaveFile('{str(wav).replace("'", "''")}')
$s.Speak(@'
{body}
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


def _wav_duration(path: Path) -> float:
    import wave

    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate() or 1)


def pack_judge_pitch() -> int:
    """Trim dead time and mux timed VO over remaining real UI (90–120s target)."""
    src = VIDEO_OUT if VIDEO_OUT.is_file() else None
    if src is None:
        print("ERROR: missing current with-audio MP4", file=sys.stderr)
        return 2
    if not shutil.which("ffmpeg"):
        print("ERROR: ffmpeg required", file=sys.stderr)
        return 2

    backup = OUT / "junctiontrace_judge_demo_with_audio.155s.mp4"
    if not backup.is_file():
        shutil.copy2(src, backup)

    work = OUT / "_pitch_work"
    work.mkdir(exist_ok=True)
    n = len(PITCH_VIDEO_CLIPS)
    parts = []
    fc = []
    for i, (a, b) in enumerate(PITCH_VIDEO_CLIPS):
        fc.append(
            f"[{i}:v]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{i}]"
        )
        parts.append(f"[v{i}]")
    fc.append(f"{''.join(parts)}concat=n={n}:v=1:a=0[vout]")
    cmd = ["ffmpeg", "-y"]
    for _ in PITCH_VIDEO_CLIPS:
        cmd.extend(["-i", str(backup)])
    cmd.extend(
        [
            "-filter_complex",
            ";".join(fc),
            "-map",
            "[vout]",
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(work / "video.mp4"),
        ]
    )
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    vinfo = _ffprobe_streams(work / "video.mp4")
    vdur = float((vinfo.get("format") or {}).get("duration") or 0)
    if not (90.0 <= vdur <= 120.0):
        # Allow slight undershoot from encoder; fail hard if far off.
        if vdur < 85 or vdur >= 180:
            print(f"ERROR: pitch duration {vdur}s not in 90–120 window", file=sys.stderr)
            return 1

    wavs = []
    joined_text = []
    for i, (start, text) in enumerate(PITCH_CUES):
        w = work / f"cue_{i}.wav"
        if not _sapi_wav(text, w):
            print("ERROR: SAPI failed for pitch cue", i, file=sys.stderr)
            return 1
        wavs.append((start, w, _wav_duration(w)))
        joined_text.append(text)

    mix = []
    labels = []
    ffmpeg = ["ffmpeg", "-y", "-i", str(work / "video.mp4")]
    for i, (start, w, _d) in enumerate(wavs):
        ffmpeg.extend(["-i", str(w)])
        delay_ms = int(round(start * 1000))
        mix.append(f"[{i+1}:a]aformat=sample_fmts=fltp:sample_rates=22050:channel_layouts=mono,adelay={delay_ms}|{delay_ms},apad=whole_dur={vdur:.3f},atrim=0:{vdur:.3f}[a{i}]")
        labels.append(f"[a{i}]")
    mix.append(f"{''.join(labels)}amix=inputs={len(wavs)}:normalize=0:dropout_transition=0,alimiter=limit=0.95,atrim=0:{vdur:.3f}[aout]")
    ffmpeg.extend(
        [
            "-filter_complex",
            ";".join(mix),
            "-map",
            "0:v",
            "-map",
            "[aout]",
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
        ]
    )
    subprocess.check_call(ffmpeg, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    info = _ffprobe_streams(VIDEO_OUT)
    streams = info.get("streams") or []
    duration = float((info.get("format") or {}).get("duration") or 0)
    types = {s.get("codec_type") for s in streams}
    full_text = " ".join(joined_text)
    ok = (
        "audio" in types
        and "video" in types
        and 85.0 < duration < 180.0
        and "NVIDIA Nemotron" in full_text
        and "Nebius Token Factory" in full_text
    )
    report = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "ok": ok,
        "decision": "B_trim_dead_time_plus_timed_vo_on_remaining_ui",
        "mp4": str(VIDEO_OUT),
        "source_155s": str(backup),
        "duration_s": duration,
        "has_audio": "audio" in types,
        "has_video": "video" in types,
        "streams": streams,
        "names_nemotron": "NVIDIA Nemotron" in full_text,
        "names_nebius_token_factory": "Nebius Token Factory" in full_text,
        "video_clips_from_155s": PITCH_VIDEO_CLIPS,
        "cues": [{"start_s": s, "text": t, "wav_s": d} for (s, _w, d), (_st, t) in zip(wavs, PITCH_CUES)],
        "youtube_url": None,
        "note": "Local competition pitch. Do not upload without owner approval.",
    }
    VERIFY.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if duration < 90 or duration > 120:
        print(f"WARNING: duration {duration:.2f}s outside 90–120 target", file=sys.stderr)
    return 0 if ok and 85 < duration <= 120 else 1


if __name__ == "__main__":
    if "--pitch" in sys.argv:
        raise SystemExit(pack_judge_pitch())
    raise SystemExit(main())
