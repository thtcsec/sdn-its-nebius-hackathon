#!/usr/bin/env bash
# Experiment A inside WSL/Linux (root).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mn -c >/dev/null 2>&1 || true
service openvswitch-switch start >/dev/null 2>&1 || true
export PYTHONPATH="$ROOT/src"
exec python3 "$ROOT/scripts/exp_a_ddos_containment.py" --hard-timeout "${1:-8}"
