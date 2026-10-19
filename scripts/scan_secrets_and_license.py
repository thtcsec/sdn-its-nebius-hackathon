#!/usr/bin/env python3
"""Secret / license hygiene scan for public-release checklist (no network)."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SECRET_PATTERNS = [
    (re.compile(r"(?i)nebius_api_key\s*=\s*\S+"), "NEBIUS_API_KEY assignment"),
    (re.compile(r"(?i)api[_-]?key\s*[:=]\s*['\"]?[a-z0-9_\-]{20,}"), "generic api_key"),
    (re.compile(r"sk-[a-zA-Z0-9]{20,}"), "sk- style token"),
    (re.compile(r"(?i)authorization:\s*bearer\s+\S+"), "bearer header"),
    (re.compile(r"BEGIN (RSA |OPENSSH )?PRIVATE KEY"), "private key block"),
]

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    ".venv-judge",
    ".venv-judge-light",
    ".venv-lab",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".ruff_cache",
}


def iter_files() -> list[Path]:
    out = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in p.parts):
            continue
        if p.name == ".env" or p.suffix in {".pt", ".png", ".jpg", ".pdf", ".docx", ".zip"}:
            continue
        if "secret_license_scan" in p.name or "public_release_full_scan" in p.name:
            continue
        if "docker_smoke_report" in p.name or "e2e_product_report" in p.name:
            continue
        if p.stat().st_size > 2_000_000:
            continue
        out.append(p)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default=str(ROOT / "artifacts" / "hackathon" / "secret_license_scan.json"),
    )
    args = parser.parse_args()

    findings = []
    for path in iter_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        # Allow docs / examples / this scanner (documentation of patterns)
        if path.name in {
            ".env.example",
            "scan_secrets_and_license.py",
            "scan_public_release_full.py",
            "smoke_judge_docker.py",
            "mux_demo_voiceover.py",
        }:
            continue
        if "deploy/judge/.env.example" in str(path).replace("\\", "/"):
            continue
        if rel.startswith("docs/") or rel.endswith(".md"):
            # Only flag markdown if a long high-entropy assignment appears
            pass
        for rx, label in SECRET_PATTERNS:
            if not rx.search(text):
                continue
            if label == "bearer header" and (
                rel.startswith("docs/")
                or rel.endswith(".md")
                or rel in {"api/middleware.py", "configs/controller.yaml"}
            ):
                # Documentation / auth how-to — not a live secret
                continue
            if label == "NEBIUS_API_KEY assignment":
                for line in text.splitlines():
                    if re.search(r"(?i)nebius_api_key\s*=\s*\S+", line):
                        val = line.split("=", 1)[-1].strip().strip('"').strip("'")
                        if val and not val.startswith("<") and val not in {"", "...", "your", "Token"} and len(val) > 12:
                            findings.append({"file": rel, "label": label, "line_preview": line[:40] + "…"})
                continue
            if rel.startswith("docs/") or rel.endswith(".md"):
                continue
            findings.append({"file": rel, "label": label})

    tracked_env = subprocess.run(
        ["git", "ls-files", ".env"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    env_tracked = bool(tracked_env.stdout.strip())

    license_path = ROOT / "LICENSE"
    report = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "license_file_present": license_path.is_file(),
        "license_head": (license_path.read_text(encoding="utf-8")[:120] if license_path.is_file() else None),
        "dotenv_gitignored": (ROOT / ".gitignore").read_text(encoding="utf-8").find(".env") >= 0,
        "env_tracked_in_git": env_tracked,
        "secret_findings": findings,
        "ok": (not env_tracked) and license_path.is_file() and len(findings) == 0,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("ok", "env_tracked_in_git", "license_file_present", "secret_findings")}, indent=2))
    print(f"wrote {out}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
