# dev.ps1 - All-In-One Developer & Demo Launcher
# Spawns SDN Resilience Controller, Automated Telemetry Streamer, and opens Web Dashboard.

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $ProjectRoot

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  SDN-ITS RESILIENCE AI - AUTOMATED LIVE DEMO LAUNCHER" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

$PythonExec = "$ProjectRoot\.venv\Scripts\python.exe"
if (-not (Test-Path $PythonExec)) {
    Write-Host "[!] Virtual environment python not found at $PythonExec" -ForegroundColor Red
    Write-Host "[*] Falling back to system python..." -ForegroundColor Yellow
    $PythonExec = "python"
}

# 1. Start SDN Resilience Controller
Write-Host "[*] Step 1: Starting SDN Controller REST API on http://127.0.0.1:8080..." -ForegroundColor Green
$ControllerJob = Start-Job -ScriptBlock {
    param($py, $root)
    Set-Location $root
    & $py "$root\sdn_controller\controller.py" --port 8080
} -ArgumentList $PythonExec, $ProjectRoot

Start-Sleep -Seconds 2

# 2. Open Web Browser
Write-Host "[*] Step 2: Opening Command Center Dashboard in Browser..." -ForegroundColor Green
Start-Process "http://127.0.0.1:8080/"

# 3. Start Automated Live Telemetry Generator
Write-Host "[*] Step 3: Starting Continuous AI Telemetry Streamer..." -ForegroundColor Green
Write-Host "[+] System Live! Watch real-time AI anomaly detection & OpenFlow mitigation in your browser." -ForegroundColor Yellow
Write-Host "[!] Press Ctrl+C in this terminal window to stop all background services.`n" -ForegroundColor Gray

try {
    & $PythonExec "$ProjectRoot\simulation\traffic_generator.py" --interval 1.5
}
finally {
    Write-Host "`n[*] Cleaning up background processes..." -ForegroundColor Yellow
    Stop-Job $ControllerJob -ErrorAction SilentlyContinue
    Remove-Job $ControllerJob -ErrorAction SilentlyContinue
    Write-Host "[+] Services stopped cleanly." -ForegroundColor Green
}
