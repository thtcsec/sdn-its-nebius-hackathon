#!/usr/bin/env python3
"""Hard-cut a real-app capture, add one SAPI voice + captions, export final MP4.

Never Ken Burns / zoompan. Never overwrite the old judge pitch MP4.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "demo_video"
FINAL = OUT / "junctiontrace_REAL_APP_DEMO.mp4"
QA_DIR = OUT / "real_app_qa"
VOICE_ID = "Microsoft David Desktop"
SAPI_RATE = -1  # restrained

# Spoken cues mapped later onto the *edited* timeline.
CUE_TEXTS = [
    "JunctionTrace investigates traffic surges before operators disrupt a junction.",
    "Safe offline uses a deterministic planner with real tools, never labeled as live Nemotron.",
    "This run calls NVIDIA Nemotron through Nebius Token Factory. Tools return evidence, then the model concludes.",
    "OpenFlow stays mocked. Camera metadata is synthetic. The policy gate remains deterministic.",
]


def ffprobe(path: Path) -> dict:
    raw = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ],
        text=True,
    )
    return json.loads(raw)


def duration(path: Path) -> float:
    return float((ffprobe(path).get("format") or {}).get("duration") or 0)


def latest_raw_dir() -> Path:
    dirs = sorted(
        [p for p in OUT.glob("real_app_raw_*") if (p / "capture_proof.json").is_file()],
        key=lambda p: p.name,
    )
    if not dirs:
        raise SystemExit("No real_app_raw_* directory found")
    return dirs[-1]


def load_proof(raw_dir: Path) -> dict:
    return json.loads((raw_dir / "capture_proof.json").read_text(encoding="utf-8"))


def event_t(proof: dict, name: str, default: float | None = None) -> float:
    for e in proof.get("events") or []:
        if e.get("name") == name:
            return float(e["t"])
    if default is not None:
        return default
    raise KeyError(name)


def keep_windows(proof: dict, src_dur: float) -> list[tuple[float, float]]:
    """Source-timeline keep ranges. Hard cuts only. Shorten live wait, keep truth."""
    ev = {e["name"]: float(e["t"]) for e in proof.get("events") or []}
    windows: list[tuple[float, float]] = []

    t_load = ev.get("page_loaded", 0.3)
    t_off_click = ev.get("click_investigate_offline", t_load + 8)
    t_off_res = ev.get("offline_result_visible", t_off_click + 2)
    t_real_click = ev.get("click_investigate_real")
    t_real_load = ev.get("real_loading_visible")
    t_real_res = ev.get("real_result_visible")
    t_end = ev.get("end_on_product", ev.get("capture_stopping", src_dur - 0.4))

    # Scene A + B through offline result board (no fabricated wait cut — offline is fast)
    a_end = min(t_off_res + 12.0, (t_real_click - 0.4) if t_real_click else t_end)
    windows.append((max(0.15, t_load - 0.1), a_end))

    if t_real_click and t_real_res:
        # Mode switch + click + first seconds of real loading (shorten the middle wait only)
        load_keep = 10.0
        pre = max(t_real_click - 6.5, a_end)
        windows.append((pre, min((t_real_load or t_real_click) + load_keep, t_real_res - 0.5)))
        # Resume just before the real result paints, through closing product shot
        windows.append((max(t_real_res - 0.8, t_real_click), min(t_end + 1.0, src_dur - 0.05)))
    elif t_real_click:
        windows.append((max(t_real_click - 5.0, a_end), min(t_end + 1.0, src_dur - 0.05)))

    # Merge overlaps / tiny gaps
    merged: list[list[float]] = []
    for a, b in windows:
        a = max(0.0, a)
        b = min(src_dur, b)
        if b - a < 0.4:
            continue
        if merged and a <= merged[-1][1] + 0.05:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged]


def concat_hard_cuts(src: Path, windows: list[tuple[float, float]], dest: Path) -> None:
    fc = []
    parts = []
    cmd = ["ffmpeg", "-y"]
    for i, (a, b) in enumerate(windows):
        cmd.extend(["-i", str(src)])
        fc.append(f"[{i}:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS,fps=30,scale=1920:1080:flags=lanczos,setsar=1,format=yuv420p[v{i}]")
        parts.append(f"[v{i}]")
    fc.append(f"{''.join(parts)}concat=n={len(windows)}:v=1:a=0[vout]")
    cmd.extend(
        [
            "-filter_complex",
            ";".join(fc),
            "-map",
            "[vout]",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            "-movflags",
            "+faststart",
            str(dest),
        ]
    )
    subprocess.check_call(cmd)


def sapi_wav(text: str, wav: Path) -> None:
    wav.parent.mkdir(parents=True, exist_ok=True)
    escaped = text.replace("'", "''")
    ps = f"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice('{VOICE_ID}')
$s.Rate = {SAPI_RATE}
$s.Volume = 90
$s.SetOutputToWaveFile('{str(wav).replace("'", "''")}')
$s.Speak(@'
{escaped}
'@)
$s.Dispose()
"""
    subprocess.check_call(["powershell", "-NoProfile", "-Command", ps])
    if not wav.is_file() or wav.stat().st_size < 1000:
        raise RuntimeError(f"SAPI failed for: {text[:40]}")


def wav_dur(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate() or 1)


def write_ass(path: Path, captions: list[tuple[float, float, str]], vdur: float) -> None:
    def ts(t: float) -> str:
        t = max(0.0, min(t, vdur))
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = t % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Segoe UI,34,&H00F2F7FF,&H000000FF,&HAA0B1220,&H88000000,0,0,0,0,100,100,0,0,1,2,0,2,70,70,42,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for a, b, text in captions:
        safe = text.replace("{", "\\{").replace("}", "\\}")
        lines.append(f"Dialogue: 0,{ts(a)},{ts(b)},Caption,,0,0,0,,{safe}\n")
    path.write_text("".join(lines), encoding="utf-8")


def mux(video: Path, wavs: list[tuple[float, Path, float]], ass: Path, dest: Path, vdur: float) -> None:
    work = ass.parent
    cmd = ["ffmpeg", "-y", "-i", str(video)]
    mix = []
    labels = []
    for i, (start, wav, _d) in enumerate(wavs):
        cmd.extend(["-i", str(wav)])
        delay = int(round(start * 1000))
        mix.append(
            f"[{i+1}:a]aformat=sample_fmts=fltp:sample_rates=22050:channel_layouts=mono,"
            f"adelay={delay}|{delay},apad=whole_dur={vdur:.3f},atrim=0:{vdur:.3f}[a{i}]"
        )
        labels.append(f"[a{i}]")
    mix.append(
        f"{''.join(labels)}amix=inputs={len(wavs)}:normalize=0:dropout_transition=0,"
        f"alimiter=limit=0.95,atrim=0:{vdur:.3f},asetpts=PTS-STARTPTS[aout]"
    )
    ass_rel = ass.name
    cmd.extend(
        [
            "-filter_complex",
            ";".join(mix),
            "-vf",
            f"ass={ass_rel}",
            "-map",
            "0:v:0",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(dest),
        ]
    )
    subprocess.check_call(cmd, cwd=str(work))


def contact_sheet(video: Path, dest_dir: Path, step: float = 4.0) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dur = duration(video)
    frames = []
    t = 0.0
    i = 0
    while t < dur:
        jpg = dest_dir / f"frame_{i:03d}_t{int(t):03d}s.jpg"
        subprocess.check_call(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{t:.2f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-q:v",
                "3",
                str(jpg),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        frames.append(jpg)
        t += step
        i += 1
    return frames


def edited_time(windows: list[tuple[float, float]], src_t: float) -> float:
    acc = 0.0
    for a, b in windows:
        if src_t < a:
            return acc
        if src_t <= b:
            return acc + (src_t - a)
        acc += b - a
    return acc


def build_captions(proof: dict, windows: list[tuple[float, float]], vdur: float) -> list[tuple[float, float, str]]:
    ev = {e["name"]: float(e["t"]) for e in proof.get("events") or []}
    real = proof.get("real") or {}
    offline = proof.get("offline") or {}

    def et(name: str, fallback_src: float) -> float:
        return edited_time(windows, ev.get(name, fallback_src))

    caps = [
        (0.4, 7.8, "JunctionTrace — investigate before disrupting a junction"),
        (et("click_scenario_a", 8), et("click_investigate_offline", 12) + 1.5, "Scenario A · legitimate congestion · Safe offline"),
        (et("offline_result_visible", 14), et("click_mode_real", 26) or et("offline_result_visible", 14) + 10, "deterministic planner (offline) — real tools, not live Nemotron"),
    ]
    if ev.get("click_mode_real"):
        live_label = "LIVE Nebius / real_api" if real.get("has_real_api") else "Labeled result — not claimed live if fallback"
        if real.get("has_real_api"):
            live_label = "LIVE Nebius / real_api"
        elif real.get("has_planner"):
            live_label = "Not live — labeled deterministic/fallback path"
        caps.append((et("click_mode_real", 28), et("click_investigate_real", 34) + 2.0, "Scenario B · Real Nebius · NVIDIA Nemotron"))
        caps.append((et("real_loading_visible", 36), min(et("real_result_visible", 50), et("real_loading_visible", 36) + 4), "Running investigation — real model wait shortened in edit"))
        caps.append((et("real_result_visible", 50), min(vdur - 16, et("real_result_visible", 50) + 12), live_label))
        compare = "Agent vs rule-only — watch observe vs rate_limit on the live board"
        if real.get("has_observe") and real.get("has_rate_limit"):
            compare = "Investigation action vs rule-only rate_limit (on-screen comparison)"
        caps.append((et("real_operator_board", vdur - 18) if "dwell_start_real_operator_board" in ev else max(vdur - 22, 0), vdur - 8, compare))
        caps.append((max(vdur - 16, 0), vdur - 0.4, "OpenFlow mocked · camera synthetic · gate deterministic"))
    else:
        caps.append((max(vdur - 12, 0), vdur - 0.4, "OpenFlow mocked · camera synthetic · gate deterministic"))
    # Clamp
    out = []
    for a, b, text in caps:
        a = max(0.0, a)
        b = min(vdur - 0.05, max(a + 1.2, b))
        if b > a:
            out.append((a, b, text))
    return out


def cue_starts(proof: dict, windows: list[tuple[float, float]], vdur: float, wav_lens: list[float]) -> list[float]:
    ev = {e["name"]: float(e["t"]) for e in proof.get("events") or []}

    def et(name: str, fb: float) -> float:
        return edited_time(windows, ev.get(name, fb))

    starts = [
        0.6,
        et("click_investigate_offline", 10) + 0.4,
        et("real_result_visible", 40) + 0.5 if ev.get("real_result_visible") else et("click_mode_real", 30) + 0.4,
        max(vdur - wav_lens[-1] - 1.2, et("dwell_start_limitations_on_result", vdur - 12)),
    ]
    # Prevent overlap
    for i in range(1, len(starts)):
        need = starts[i - 1] + wav_lens[i - 1] + 0.35
        if starts[i] < need:
            starts[i] = need
        if starts[i] + wav_lens[i] > vdur - 0.15:
            starts[i] = max(0.0, vdur - wav_lens[i] - 0.15)
    return starts


def transcode_webm(webm: Path, mp4: Path) -> None:
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
            "-r",
            "30",
            "-an",
            str(mp4),
        ]
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=str, default="")
    args = parser.parse_args()
    raw_dir = Path(args.raw_dir) if args.raw_dir else latest_raw_dir()
    proof = load_proof(raw_dir)
    grab = Path(proof["gdigrab"]) if proof.get("gdigrab") else None
    webm = Path(proof["playwright_webm"]) if proof.get("playwright_webm") else None
    work = raw_dir / "edit_work"
    work.mkdir(exist_ok=True)

    src = None
    source_kind = None
    if grab and grab.is_file() and grab.stat().st_size > 100_000:
        src = grab
        source_kind = "ffmpeg_gdigrab_desktop"
    elif webm and webm.is_file():
        src = work / "playwright_source.mp4"
        transcode_webm(webm, src)
        source_kind = "playwright_viewport"
    else:
        print("ERROR: no usable source recording", file=sys.stderr)
        return 1

    src_dur = duration(src)
    windows = keep_windows(proof, src_dur)
    cut = work / "hardcuts.mp4"
    concat_hard_cuts(src, windows, cut)
    vdur = duration(cut)
    if vdur > 180:
        print(f"ERROR: edited duration {vdur:.1f}s > 180", file=sys.stderr)
        return 1

    wavs_meta = []
    speech_total = 0.0
    for i, text in enumerate(CUE_TEXTS):
        w = work / f"cue_{i}.wav"
        sapi_wav(text, w)
        d = wav_dur(w)
        wavs_meta.append((text, w, d))
        speech_total += d

    starts = cue_starts(proof, windows, vdur, [d for _, _, d in wavs_meta])
    placed = [(starts[i], wavs_meta[i][1], wavs_meta[i][2]) for i in range(len(wavs_meta))]

    ass = work / "captions.ass"
    write_ass(ass, build_captions(proof, windows, vdur), vdur)

    mux(cut, placed, ass, FINAL, vdur)
    frames = contact_sheet(FINAL, QA_DIR / "contact", step=5.0)

    verify = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "final": str(FINAL),
        "source_kind": source_kind,
        "source_path": str(src),
        "raw_dir": str(raw_dir),
        "keep_windows_source": windows,
        "edited_duration_s": duration(FINAL),
        "ffprobe": ffprobe(FINAL),
        "voice_engine": "Windows SAPI System.Speech.Synthesis.SpeechSynthesizer",
        "voice_id": VOICE_ID,
        "sapi_rate": SAPI_RATE,
        "speaker_count": 1,
        "cue_texts": CUE_TEXTS,
        "cue_starts_s": starts,
        "speech_total_s": speech_total,
        "captions_ass": str(ass),
        "contact_frames": [str(p) for p in frames],
        "offline": proof.get("offline"),
        "real": proof.get("real"),
        "capabilities": proof.get("capabilities"),
        "effects": "hard_cuts_plus_captions_only_no_zoompan",
    }
    (work / "edit_verify.json").write_text(json.dumps(verify, indent=2), encoding="utf-8")
    (QA_DIR / "edit_verify.json").write_text(json.dumps(verify, indent=2), encoding="utf-8")
    print(json.dumps({k: verify[k] for k in ("final", "source_kind", "edited_duration_s", "voice_id", "speech_total_s", "cue_starts_s")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
