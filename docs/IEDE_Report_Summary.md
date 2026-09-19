# Tsinghua University IEDE Research Proposal Summary

**Project Title:** AI-Assisted Resilience for SDN-Enabled Intelligent Transportation Systems  
**Subtitle:** Network Anomaly Detection, Reversible Mitigation, and Camera-Assisted Physical Context  
**Academic Context:** Innovation and Entrepreneurship Development Education (IEDE) Autumn Semester 2026, Tsinghua University, Beijing, China  
**Author:** Trinh Hoang Tu  
**Project Advisor:** Professor Kris Singh (Visiting Professor at Tsinghua University; CEO at SRII, Silicon Valley)

> **Cite from** `artifacts/results/` (InSDN / CIC / Exp A–D).  
> See [REPRODUCE.md](REPRODUCE.md) and [EVIDENCE.md](EVIDENCE.md). Console defaults to **Lab mode**.  
> Camera = independent physical observation of the **same RSU service zone**; not a DDoS detector.

---

## Executive Summary & Research Motivation
The protected asset is **RSU-based ITS/V2X connectivity**. An attacker aims to exhaust control-plane or edge-network resources and degrade legitimate vehicle-to-infrastructure communication. SDN enables programmable mitigation, but permanent DROP/blacklist responses can also harm legitimate mobility traffic during rush-hour surges that elevate the same coarse counters used for intrusion signals.

This research proposes **SDN mitigation informed by physical context from the same RSU zone**: flow-level telemetry, lightweight TCN-GRU detection, temporary OpenFlow containment with rollback, and an optional roadside camera that helps the policy test whether abnormal *network* demand is consistent with observable transportation activity.

---

## Core Research Questions (RQs)
- **RQ1**: How can SDN telemetry detect abnormal behavior in ITS networks without resource-intensive deep packet inspection (DPI)?
- **RQ2**: Can a lightweight TCN-GRU model satisfy prototype edge-level latency and memory constraints while maintaining **useful in-domain** anomaly-detection performance?
- **RQ3**: How can closed-loop SDN mitigation reduce controller overload while minimizing false-positive disruption to legitimate transportation services?
- **RQ4**: How should public security datasets (InSDN, **CIC-IDS2017**) be combined with simulated VANET scenarios to approximate ITS network behavior?

---

## Evaluation Metrics Summary
1. **Detection Quality**: Accuracy, Precision, Recall, F1-Score, ROC-AUC (classifier head).
2. **False Alarm Control**: FPR / FNR; fusion-corrected false blocks (policy-level).
3. **Latency**: $t_{inference}$, $IDL$, $T_{\text{response}}$ (tracked eval path).
4. **Controller / dataplane**: PacketIn proxies where available; ICMP delivery ratios (Exp A).
5. **Transportation continuity**: Legitimate delivery under temporary vs permanent DROP.
6. **Mitigation side effects**: Cooldown rollback success; rush-hour preserve path.

---

## Tracked prototype snapshot (primary claims)

Numbers below are from tracked JSON under `artifacts/results/` (refresh via `scripts/sync_artifacts.ps1`).  
Do **not** cite older synthetic multiclass “97% / 100%” prototype figures.

### 1. Classifier head — **binary** Normal vs Anomaly (not 5-class macro)
- **Acc** ≈ **96.2%** · **F1** ≈ **0.977** · **AUC** ≈ **0.977**  
  Definition: `cls_binary_*` = `(argmax class > 0)`; sklearn `average="binary"`.  
  `roc_auc` = binary score `sum(P(class ≠ Normal))`.  
  Source: `artifacts/results/exp_insdn/metrics.json`.  
  See [METHODOLOGY.md](METHODOLOGY.md) for macro/weighted multiclass exports.

### 2. Cross-dataset (InSDN → CIC-IDS2017 adapt)
- Zero-shot holdout Acc ≈ **71.5%** → adapted Acc ≈ **98.6%** (ΔF1 ≈ **+0.35**)  
  Source: `artifacts/results/cross_dataset/adapted_metrics.json`.
  Dataset id: `cicids2017` (not CSE-CIC-IDS2018).

### 3. Latency (same InSDN eval export)
- **Inference** ≈ **0.25 ms** · **IDL** ≈ **6.45 ms** · **$T_{\text{response}}$** ≈ **9.95 ms**  
  Source: `exp_insdn/metrics.json` (`inference_ms`, `idl_ms`, `t_response_ms`).

### 4. Lab evidence (scripts, not the console mock path)
| Exp | Claim | Artifact |
|-----|-------|----------|
| **A** | Reversible DROP vs permanent / none (ICMP + ovs-ofctl) | `artifacts/results/exp_a/` |
| **B/C** | Explainable camera×network fusion rules | `artifacts/results/exp_bc/` |
| **D** | Graded camera/tracker × fusion phases | `artifacts/results/exp_d/` |

Honesty: Windows default OpenFlow is **mock** (`NET · NO EVIDENCE`). Real switch evidence needs `SDN_OF_BACKEND=http|ryu` + lab checklist.
