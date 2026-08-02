#Requires -Version 5.1
<#
.SYNOPSIS
  Materialize artifacts/ + dataset manifests for a reproducible package.
#>
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")

$dirs = @(
    "artifacts\models",
    "artifacts\results\exp_insdn",
    "artifacts\results\cross_dataset",
    "artifacts\results\ablation",
    "datasets\manifests"
)
foreach ($d in $dirs) {
    New-Item -ItemType Directory -Force -Path (Join-Path $Root $d) | Out-Null
}

# Copy lightweight evidence into artifacts/
$copies = @(
    @{ Src = "results\tcn_gru\eval_metrics.json"; Dst = "artifacts\results\exp_insdn\metrics.json" },
    @{ Src = "results\tcn_gru\confusion_matrix.png"; Dst = "artifacts\results\exp_insdn\confusion_matrix.png" },
    @{ Src = "results\cross_dataset\adapted_metrics.json"; Dst = "artifacts\results\cross_dataset\adapted_metrics.json" },
    @{ Src = "results\cross_dataset\eval_metrics.json"; Dst = "artifacts\results\cross_dataset\eval_metrics.json" },
    @{ Src = "results\ablation\ablation_report.json"; Dst = "artifacts\results\ablation\ablation_report.json" },
    @{ Src = "results\ablation\ablation.json"; Dst = "artifacts\results\ablation\ablation.json" }
)
foreach ($c in $copies) {
    $src = Join-Path $Root $c.Src
    $dst = Join-Path $Root $c.Dst
    if (Test-Path $src) {
        Copy-Item -LiteralPath $src -Destination $dst -Force
        Write-Host " [+] $($c.Dst)"
    } else {
        Write-Host " [!] missing $($c.Src)" -ForegroundColor Yellow
    }
}

# Model card (honest about what is / isn't in the zip)
$ckpt = Join-Path $Root "models\checkpoints\tcn_gru_best.pt"
$card = @{
    name            = "tcn_gru_resilience"
    version         = "0.2.0"
    arch            = "TCN-GRU"
    checkpoint_path = "models/checkpoints/tcn_gru_best.pt"
    checkpoint_present = [bool](Test-Path $ckpt)
    scaler_path     = "models/checkpoints/scaler.joblib"
    feature_order   = @(
        "flow_duration", "packet_rate", "byte_rate", "pkt_iat_mean", "pkt_iat_std",
        "packet_len_mean", "packet_in_count", "tcp_flags_syn_count", "flow_active_ratio",
        "rsu_channel_occupancy"
    )
    label_mapping   = @{
        "0" = "Normal"
        "1" = "DDoS_PacketIn_Flood"
        "2" = "LOFT_LowRate_Attack"
        "3" = "RSU_Link_Fault"
        "4" = "RushHour_Burst"
    }
    primary_metrics_ref = "artifacts/results/exp_insdn/metrics.json"
    notes           = @(
        "Prefer classifier-head binary metrics over RE-threshold alone.",
        "Synthetic 100% multiclass is not strong evidence — cite InSDN/CIC tables.",
        "Checkpoint *.pt excluded from default zip; train or use -IncludeCheckpoint."
    )
    updated_utc     = (Get-Date).ToUniversalTime().ToString("o")
} | ConvertTo-Json -Depth 6

Set-Content -Path (Join-Path $Root "artifacts\models\model_card.json") -Value $card -Encoding UTF8

$manifest = @{
    datasets = @(
        @{
            id = "canonical_sample"
            path = "datasets/sample/canonical_flows.csv"
            role = "demo_csv"
            notes = "Small canonical sample for smoke train / console"
        },
        @{
            id = "insdn_shaped_sample"
            path = "datasets/sample/insdn_shaped_sample.csv"
            role = "demo_csv"
        },
        @{
            id = "insdn_windows"
            path = "datasets/processed/insdn_windows.npz"
            role = "train_eval"
            in_default_zip = $false
            prepare = "python scripts/download_dataset.py --name insdn --prepare"
        },
        @{
            id = "cic_windows"
            path = "datasets/processed/cic_windows.npz"
            role = "cross_dataset"
            in_default_zip = $false
            prepare = "python scripts/download_dataset.py --name cicids2017 --prefer hf --prepare"
        }
    )
} | ConvertTo-Json -Depth 6
Set-Content -Path (Join-Path $Root "datasets\manifests\datasets.json") -Value $manifest -Encoding UTF8

@"
# Artifacts

Paper-facing evidence mirrors (metrics JSON / confusion matrices).

- ``models/model_card.json`` — checkpoint metadata (weights may be local-only)
- ``results/exp_insdn/`` — InSDN in-domain eval
- ``results/cross_dataset/`` — CIC zero-shot / adapted
- ``results/ablation/`` — architecture sweep outputs if present

Rebuild mirrors: ``.\scripts\sync_artifacts.ps1``
Reproduce tables: ``.\reproduce.ps1``
"@ | Set-Content -Path (Join-Path $Root "artifacts\README.md") -Encoding UTF8

Write-Host "[*] sync_artifacts done"
