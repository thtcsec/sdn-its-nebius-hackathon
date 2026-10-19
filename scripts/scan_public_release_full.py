#!/usr/bin/env python3
"""Comprehensive secret/license scan: working tree, git history, binary media.

Does not claim public release readiness — reports facts only.
"""

from __future__ import annotations

import json
import re
import subprocess
import struct
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "hackathon" / "public_release_full_scan.json"

PATTERNS = [
    (re.compile(r"(?i)nebius_api_key\s*=\s*([^\s#]+)"), "NEBIUS_API_KEY assignment"),
    (re.compile(r"sk-[a-zA-Z0-9]{24,}"), "sk- style token"),
    (re.compile(r"v1\.CmQK[A-Za-z0-9_\-\.]{30,}"), "nebius-like v1.CmQK token"),
    (re.compile(r"BEGIN (RSA |OPENSSH )?PRIVATE KEY"), "private key block"),
]

SKIP_PARTS = {".git", ".venv", ".venv-judge-light", "__pycache__", "node_modules"}
SKIP_FILES = {
    "scan_public_release_full.py",
    "scan_secrets_and_license.py",
    "smoke_judge_docker.py",
    "mux_demo_voiceover.py",
    "secret_license_scan.json",
    "public_release_full_scan.json",
}


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)
    return (r.stdout or "") + (r.stderr or "")


def _is_placeholder_value(val: str) -> bool:
    v = (val or "").strip().strip("'\"").strip("`")
    if not v:
        return True
    low = v.lower()
    if low in {"...", "token", "your", "$nebius_api_key"}:
        return True
    if v.startswith("<") or v.startswith("$") or v.startswith("{"):
        return True
    if "replace" in low or "example" in low or "your-" in low or "nebius_key" in low:
        return True
    if v.endswith("...") or v == "...":
        return True
    # Require substantial entropy-looking values for API keys
    if len(v) < 20:
        return True
    return False


def scan_tree() -> list[dict]:
    findings = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_PARTS for part in p.parts):
            continue
        if p.name in {".env", ".env.smoke"} or p.name in SKIP_FILES:
            continue
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".webm", ".wav", ".pt", ".zip"}:
            continue
        if p.stat().st_size > 2_000_000:
            continue
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        if rel.endswith(".env.example") or rel.startswith("docs/"):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for rx, label in PATTERNS:
            for i, line in enumerate(text.splitlines(), 1):
                m = rx.search(line)
                if not m:
                    continue
                if "assignment" in label.lower():
                    val = m.group(1) if m.lastindex else line.split("=", 1)[-1]
                    if _is_placeholder_value(val):
                        continue
                findings.append({"file": rel, "line": i, "label": label, "preview": line[:60]})
    return findings


def scan_history() -> list[dict]:
    findings = []
    # Only flag history hits that look like real key material (long alnum values).
    log = _git(
        "log",
        "-n",
        "120",
        "--all",
        "-G",
        r"(sk-[A-Za-z0-9]{24,}|v1\.CmQK[A-Za-z0-9_\-\.]{30,}|BEGIN (RSA |OPENSSH )?PRIVATE KEY|nebius_api_key\s*=\s*[A-Za-z0-9_\.\-]{24,})",
        "-p",
        "--",
        ".env",
        "*.env",
        "*.yml",
        "*.yaml",
        "*.json",
        "*.py",
        "*.txt",
    )
    for rx, label in PATTERNS:
        for m in rx.finditer(log):
            snippet = m.group(0)
            if "assignment" in label.lower():
                val = m.group(1) if m.lastindex else snippet.split("=", 1)[-1]
                if _is_placeholder_value(val):
                    continue
            elif "nebius-like" in label or "sk-" in label:
                if len(snippet) < 28:
                    continue
            findings.append({"source": "git_history", "label": label, "preview": snippet[:48]})
            if len(findings) >= 20:
                break
    tracked = _git("ls-files", ".env", "deploy/judge/.env").strip()
    if tracked:
        findings.append({"source": "git_ls_files", "label": "tracked_env", "preview": tracked[:80]})
    return findings


def _png_has_text_chunks(path: Path) -> list[str]:
    hits = []
    try:
        data = path.read_bytes()
    except Exception:
        return hits
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return hits
    pos = 8
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        ctype = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        pos = pos + 12 + length
        if ctype in (b"tEXt", b"iTXt", b"zTXt"):
            try:
                text = chunk.decode("latin-1", errors="ignore")
            except Exception:
                continue
            if re.search(r"(?i)(api[_-]?key|bearer|sk-|password|secret\s*=)", text):
                hits.append(text[:80])
        if ctype == b"IEND":
            break
    return hits


def scan_media() -> list[dict]:
    findings = []
    for d in (ROOT / "artifacts" / "hackathon" / "product_screens", ROOT / "artifacts" / "demo_video"):
        if not d.is_dir():
            continue
        for p in d.rglob("*"):
            if not p.is_file():
                continue
            rel = str(p.relative_to(ROOT)).replace("\\", "/")
            if p.suffix.lower() == ".png":
                for h in _png_has_text_chunks(p):
                    findings.append({"file": rel, "label": "png_text_chunk_suspicious", "preview": h})
            if p.suffix.lower() in {".mp4", ".webm", ".wav"} and p.stat().st_size > 200_000_000:
                findings.append({"file": rel, "label": "oversized_media", "preview": f"size={p.stat().st_size}"})
    return findings


def main() -> int:
    tree = scan_tree()
    hist = scan_history()
    media = scan_media()
    license_ok = (ROOT / "LICENSE").is_file()
    report = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "license_present": license_ok,
        "working_tree_findings": tree,
        "git_history_findings": hist,
        "binary_media_findings": media,
        "host_or_public_release_claimed": False,
        "ok_for_private_continue": license_ok and len(tree) == 0 and len(hist) == 0 and len(media) == 0,
        "note": (
            "ok_for_private_continue means no live-looking secrets found in tree/history/media. "
            "It does NOT mean public release, host deploy, YouTube, or Devpost are approved."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok_for_private_continue": report["ok_for_private_continue"],
                "tree": len(tree),
                "history": len(hist),
                "media": len(media),
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0 if report["ok_for_private_continue"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
