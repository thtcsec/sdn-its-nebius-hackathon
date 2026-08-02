"""Deprecated — use scripts/package.ps1 or scripts/package.bat instead."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PS1 = HERE / "package.ps1"


def main() -> int:
    print("[!] scripts/package.py is deprecated.")
    print("[*] Prefer:  .\\scripts\\package.ps1   or   .\\scripts\\package.bat")
    if not PS1.exists():
        print(f"[x] Missing {PS1}")
        return 1
    if sys.platform.startswith("win"):
        cmd = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PS1),
            *sys.argv[1:],
        ]
        return subprocess.call(cmd)
    print("[x] On non-Windows, run the PowerShell script via pwsh, or zip manually.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
