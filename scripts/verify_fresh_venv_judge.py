#!/usr/bin/env python3
"""Create/use a light fresh venv and prove judge path without private assets.

Checks:
  - no 1.cameras.json required
  - no tcn_gru_best.pt required
  - judge demo + heldout rule-only eval run
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import venv
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv-judge-fresh"


def run(cmd: list[str], *, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True, check=False)


def main() -> int:
    if not VENV.exists():
        venv.EnvBuilder(with_pip=True).create(VENV)
    py = str(VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
    pip = run([py, "-m", "pip", "install", "-q", "python-dotenv>=1.0", "requests>=2.31", "pyyaml>=6", "Flask>=2.3", "pytest>=7"])
    if pip.returncode != 0:
        print(pip.stderr)
        return 1

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + str(ROOT)
    # Ensure we do not require private camera inventory
    private_cam = (ROOT / "1.cameras.json").exists()
    ckpt = (ROOT / "models" / "checkpoints" / "tcn_gru_best.pt").exists()

    steps = {}
    for name, args in [
        ("judge_demo", [py, "scripts/run_judge_demo.py"]),
        ("heldout_rule_only", [py, "scripts/run_heldout_eval.py", "--skip-real"]),
        ("pytest_hackathon", [py, "-m", "pytest", "tests/test_hackathon_agent.py", "tests/test_nebius_llm.py", "-q"]),
    ]:
        proc = run(args, env=env)
        steps[name] = {
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-500:],
            "stderr_tail": (proc.stderr or "")[-500:],
        }

    report = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "venv": str(VENV),
        "private_camera_inventory_present": private_cam,
        "classifier_checkpoint_present": ckpt,
        "note": "Judge path must succeed even if checkpoint/camera inventory are absent.",
        "steps": steps,
        "ok": all(s["returncode"] == 0 for s in steps.values()),
    }
    out = ROOT / "artifacts" / "hackathon" / "fresh_venv_judge_verify.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "checkpoint_present": ckpt, "camera_inventory_present": private_cam, "out": str(out)}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
