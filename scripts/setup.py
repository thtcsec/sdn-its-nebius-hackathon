#!/usr/bin/env python
"""Editable install + sanity checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    cmds = [
        [sys.executable, "-m", "pip", "install", "-e", str(ROOT)],
        [sys.executable, "-m", "pip", "install", "-q", "huggingface_hub"],
        [
            sys.executable,
            "-c",
            "import sdn_its; print('sdn_its', sdn_its.__version__)",
        ],
    ]
    for cmd in cmds:
        print("+", " ".join(cmd))
        subprocess.check_call(cmd, cwd=str(ROOT))
    print("[+] Setup complete.")
    print("    python scripts/download_dataset.py --name insdn --prefer hf --prepare")
    print("    python -m sdn_its.ai.train --csv datasets/sample/canonical_flows.csv")


if __name__ == "__main__":
    main()
