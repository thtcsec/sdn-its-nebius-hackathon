#Requires -Version 5.1
<#
.SYNOPSIS
  Pack a reproducible research zip matching README layout (no venv / raw dumps).

.EXAMPLE
  .\scripts\package.ps1
  .\scripts\package.ps1 -IncludeCheckpoint
#>
param(
    [string]$OutName = "sdn_its_resilience_ai_submission.zip",
    [switch]$IncludeCheckpoint
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$OutZip = Join-Path $Root $OutName
$Staging = Join-Path $env:TEMP ("sdn_its_pkg_" + [guid]::NewGuid().ToString("N"))

# Must match README tree so reviewers don't see a hollow demo zip
$IncludeDirs = @(
    "src",
    "api",
    "dashboard",
    "configs",
    "tests",
    "docs",
    "benchmark",
    "experiments",
    "models",
    "datasets",
    "results",
    "docker",
    ".github",
    "notebooks",
    "visualization",
    "artifacts",
    "assets\images\report",
    "scripts"
)

$IncludeFiles = @(
    "pyproject.toml",
    "README.md",
    "LICENSE",
    ".gitignore",
    "requirements.txt",
    "reproduce.ps1",
    "reproduce.sh"
)

$ExcludeDirNames = @(
    ".git", ".venv", ".venv-lab", "__pycache__", ".pytest_cache", ".mypy_cache",
    "node_modules", ".ruff_cache", "raw", "*.egg-info"
)

# Heavy binaries excluded by default (opt-in checkpoint)
$ExcludeFileGlobs = @(
    "*.pyc", "*.pyo", "*.log", "*.zip",
    "*.onnx", "*.npz", "*.npy", "*.h5", "*.parquet", "*.pcap", "*.pcapng",
    "*.docx", "*.pdf", ".DS_Store", "Thumbs.db",
    "_docx3_extract.txt"
)

if (-not $IncludeCheckpoint) {
    $ExcludeFileGlobs += @("*.pt", "*.pth")
}

$ExcludeScriptNames = @("package.py")

function Test-ExcludedFile([string]$FullPath) {
    $name = Split-Path $FullPath -Leaf
    foreach ($g in $ExcludeFileGlobs) {
        if ($name -like $g) { return $true }
    }
    if ($ExcludeScriptNames -contains $name) { return $true }
    # Never ship multi-GB raw / processed dumps
    if ($FullPath -match '[\\/]datasets[\\/]raw[\\/]') { return $true }
    if ($FullPath -match '[\\/]datasets[\\/]processed[\\/].*\.npz$') { return $true }
    # Console scratch reports ok; skip huge local dumps if any
    if ($FullPath -match '[\\/]results[\\/]console[\\/]') { return $true }
    return $false
}

function Copy-TreeFiltered([string]$SrcRel) {
    $src = Join-Path $Root $SrcRel
    if (-not (Test-Path $src)) {
        Write-Host "[!] skip missing: $SrcRel" -ForegroundColor Yellow
        return
    }
    $dst = Join-Path $Staging $SrcRel
    New-Item -ItemType Directory -Force -Path $dst | Out-Null

    Get-ChildItem -Path $src -Recurse -Force | ForEach-Object {
        $rel = $_.FullName.Substring($src.Length).TrimStart('\', '/')
        $parts = $rel -split '[\\/]'
        foreach ($p in $parts) {
            if ($ExcludeDirNames -contains $p) { return }
            if ($p -like "*.egg-info") { return }
        }
        if ($_.PSIsContainer) {
            $targetDir = Join-Path $dst $rel
            if (-not (Test-Path $targetDir)) {
                New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
            }
            return
        }
        if (Test-ExcludedFile $_.FullName) { return }
        $target = Join-Path $dst $rel
        $parent = Split-Path $target -Parent
        if (-not (Test-Path $parent)) {
            New-Item -ItemType Directory -Force -Path $parent | Out-Null
        }
        Copy-Item -LiteralPath $_.FullName -Destination $target -Force
    }
}

Write-Host "============================================================"
Write-Host " SDN-ITS research packager"
Write-Host " Root: $Root"
Write-Host " Checkpoint in zip: $IncludeCheckpoint"
Write-Host "============================================================"

# Ensure artifacts + manifests exist before packing
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "sync_artifacts.ps1") | Out-Host

if (Test-Path $Staging) { Remove-Item -Recurse -Force $Staging }
New-Item -ItemType Directory -Force -Path $Staging | Out-Null

foreach ($d in $IncludeDirs) { Copy-TreeFiltered $d }

foreach ($f in $IncludeFiles) {
    $src = Join-Path $Root $f
    if (Test-Path $src) {
        Copy-Item -LiteralPath $src -Destination (Join-Path $Staging $f) -Force
        Write-Host " [+] $f"
    }
}

@"
# Package contents

This zip mirrors the README research layout:

- ``benchmark/``, ``experiments/``, ``models/``, ``datasets/`` (sample + manifests),
  ``results/`` (metrics JSON/PNG), ``docker/``, ``.github/``, ``notebooks/``,
  ``visualization/``, ``artifacts/``

Excluded by default (rebuild locally or use ``-IncludeCheckpoint``):

- ``.venv``, ``__pycache__``, ``.git``
- ``datasets/raw``, large ``*.npz`` under processed
- ``*.pt`` checkpoints (unless ``-IncludeCheckpoint``)
- Word/PDF binaries, console scratch under ``results/console/``

Reproduce paper tables (needs checkpoint locally):

```powershell
.\reproduce.ps1
```

Honesty: Windows OF default is mock; Lab mode + ``SDN_OF_BACKEND=http`` for real ovs-ofctl.
"@ | Set-Content -Path (Join-Path $Staging "PACKAGING.md") -Encoding UTF8

if (Test-Path $OutZip) { Remove-Item -Force $OutZip }
Compress-Archive -Path (Join-Path $Staging "*") -DestinationPath $OutZip -CompressionLevel Optimal

$fileCount = (Get-ChildItem -Path $Staging -Recurse -File).Count
$sizeMb = [math]::Round((Get-Item $OutZip).Length / 1MB, 2)
Remove-Item -Recurse -Force $Staging

Write-Host "============================================================"
Write-Host " [+] Created: $OutZip"
Write-Host "     Size:    $sizeMb MB"
Write-Host "     Files:   $fileCount"
Write-Host "============================================================"
