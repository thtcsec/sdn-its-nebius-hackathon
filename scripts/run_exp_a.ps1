# Experiment A launcher (Windows → WSL Mininet)
# Usage:
#   .\scripts\run_exp_a.ps1           # live WSL run
#   .\scripts\run_exp_a.ps1 -DryRun   # schema only on Windows

param(
    [switch]$DryRun,
    [string]$Distro = "Ubuntu",
    [int]$HardTimeout = 8
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "py" }

if ($DryRun) {
    & $Py scripts\exp_a_ddos_containment.py --dry-run
    exit $LASTEXITCODE
}

$WslRoot = ($Root -replace '\\', '/') -replace '^([A-Za-z]):', { "/mnt/$($args[0].Groups[1].Value.ToLower())" }
# Fallback path style for D:\...
if ($Root -match '^([A-Za-z]):\\(.*)$') {
    $drive = $Matches[1].ToLower()
    $rest = ($Matches[2] -replace '\\', '/')
    $WslRoot = "/mnt/$drive/$rest"
}

Write-Host "[exp_a] WSL root: $WslRoot"
Write-Host "[exp_a] Starting Mininet containment experiment (needs root in WSL)…"

$cmd = @"
set -e
cd '$WslRoot'
mn -c >/dev/null 2>&1 || true
service openvswitch-switch start >/dev/null 2>&1 || true
export PYTHONPATH='$WslRoot/src'
python3 scripts/exp_a_ddos_containment.py --hard-timeout $HardTimeout
"@

wsl -d $Distro -u root -- bash -lc $cmd
$code = $LASTEXITCODE

$out = Join-Path $Root "experiments\exp02_ddos\results\exp_a_metrics.json"
if (Test-Path $out) {
    Write-Host "[exp_a] Results: $out"
    Get-Content $out -TotalCount 40
} else {
    Write-Host "[exp_a] No results file — WSL run may have failed (exit $code)."
}
exit $code
