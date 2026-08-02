#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-}"
CKPT="${1:-models/checkpoints/tcn_gru_best.pt}"
NPZ="${2:-datasets/processed/insdn_windows.npz}"

echo "=== SDN-ITS reproduce-paper ==="
if [[ ! -f "$CKPT" ]]; then
  echo "[x] Missing checkpoint: $CKPT"
  exit 1
fi

python -m sdn_its.ai.evaluate --checkpoint "$CKPT" --npz "$NPZ"
python -m benchmark.run_all || true
pwsh -NoProfile -File ./scripts/sync_artifacts.ps1 2>/dev/null || true
echo "=== done — see artifacts/results/ ==="
