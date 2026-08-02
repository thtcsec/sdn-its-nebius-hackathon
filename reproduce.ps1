#Requires -Version 5.1
<#
.SYNOPSIS
  One-shot paper table reproduction (needs checkpoint + processed NPZ locally).
#>
param(
    [string]$Checkpoint = "models/checkpoints/tcn_gru_best.pt",
    [string]$Npz = "datasets/processed/insdn_windows.npz"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:CUDA_VISIBLE_DEVICES = ""

Write-Host "=== SDN-ITS reproduce-paper ==="

if (-not (Test-Path $Checkpoint)) {
    Write-Host "[x] Missing checkpoint: $Checkpoint"
    Write-Host "    Train first: python -m sdn_its.ai.train --npz $Npz"
    exit 1
}

Write-Host "[*] Evaluate InSDN holdout..."
python -m sdn_its.ai.evaluate --checkpoint $Checkpoint --npz $Npz
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path "datasets/processed/cic_windows.npz") {
    Write-Host "[*] Cross-dataset eval (if script present)..."
    if (Test-Path "scripts/run_cross_dataset.py") {
        python scripts/run_cross_dataset.py
    }
}

Write-Host "[*] Micro-benchmark..."
python -m benchmark.run_all

Write-Host "[*] Sync artifacts/ ..."
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\sync_artifacts.ps1

$manifest = @{
    generated_utc = (Get-Date).ToUniversalTime().ToString("o")
    checkpoint = $Checkpoint
    npz = $Npz
    git = (git rev-parse HEAD 2>$null)
    outputs = @(
        "results/tcn_gru/eval_metrics.json",
        "artifacts/results/exp_insdn/metrics.json",
        "artifacts/models/model_card.json"
    )
} | ConvertTo-Json -Depth 4
New-Item -ItemType Directory -Force -Path "artifacts\results\exp_insdn" | Out-Null
Set-Content -Path "artifacts\results\exp_insdn\run_manifest.json" -Value $manifest -Encoding UTF8

Write-Host "=== done — see artifacts/results/ ==="
