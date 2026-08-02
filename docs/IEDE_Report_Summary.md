# Tsinghua University IEDE Research Proposal Summary

**Project Title:** AI-Assisted Resilience for SDN-Enabled Intelligent Transportation Systems: A Lightweight Framework for V2X Network Reliability, Edge Telemetry, and Safety-Aware Mitigation  
**Academic Context:** Innovation and Entrepreneurship Development Education (IEDE) Autumn Semester 2026, Tsinghua University, Beijing, China  
**Author:** Trinh Hoang Tu
**Project Advisor:** Professor Kris Singh (Visiting Professor at Tsinghua University; CEO at SRII, Silicon Valley)  

> **Evidence note (repo):** Prefer classifier-head metrics under `artifacts/results/` (InSDN / CIC).  
> Synthetic multiclass figures below are historical prototype numbers — not the primary claim.  
> See [REPRODUCE.md](REPRODUCE.md) and [EVIDENCE.md](EVIDENCE.md). Console defaults to **Lab mode**.

---

## Executive Summary & Research Motivation
Intelligent Transportation Systems (ITS) heavily depend on Vehicle-to-Everything (V2X) communication, roadside units (RSUs), edge nodes, and software-defined network control. Software-Defined Networking (SDN) centralizes network programmability, but creates a single point of failure if the SDN controller, northbound API, or control channel comes under load, misconfiguration, or cyber-attack.

This research introduces a **transportation-first resilience framework** combining flow-level telemetry, lightweight time-series deep learning (TCN-GRU), and safety-aware closed-loop SDN flow modifications.

---

## Core Research Questions (RQs)
- **RQ1**: How can SDN telemetry detect abnormal behavior in ITS networks without resource-intensive deep packet inspection (DPI)?
- **RQ2**: Can a lightweight time-series AI model detect control-plane flooding, abnormal flow behavior, and network faults under edge latency constraints?
- **RQ3**: How can closed-loop SDN mitigation reduce controller overload while minimizing false-positive disruption to legitimate transportation services?
- **RQ4**: How should public security datasets (InSDN, CSE-CIC-IDS2018) be combined with simulated VANET scenarios to approximate ITS network behavior?

---

## Evaluation Metrics Summary
1. **Detection Quality**: Accuracy, Precision, Recall, F1-Score, ROC-AUC.
2. **False Alarm Control**: False Positive Rate (FPR) vs False Negative Rate (FNR).
3. **Latency Benchmarks**: $IDL$ (Intrusion Detection Latency) and $T_{\text{response}}$ (End-to-End Response Latency).
4. **Controller Resilience**: packet_in rate reduction, Controller CPU/Memory load.
5. **Transportation Continuity**: Packet delivery ratio (PDR), RSU availability, service recovery time.
6. **Mitigation Side Effects**: Legitimate flow drop rate, cooldown expiry rollback success rate.

---

## 🔬 Prototype Implementation & Benchmarking Results

The TCN-GRU model was trained on synthetic edge network V2X telemetry sequences ($L = 10$ sequence length, $10$ features) and evaluated under cybersecurity stressor injections (DDoS, LOFT, Link Faults, and RushHour surges).

### 1. Detection Quality (After Threshold Refinement)
- **Anomaly Detection Accuracy**: **97.33%**
- **Anomaly Detection Recall**: **100.00%** (All injected cyber-attacks and faults successfully triggered the adaptive threshold $\tau = \mu_{RE} + 2\sigma_{RE}$)
- **Anomaly Detection Precision**: **93.85%**
- **Anomaly Detection F1-Score**: **96.83%**
- **Multi-Class Classification Accuracy**: **100.00%** (Perfect class separation across Normal, DDoS, LOFT, Link Fault, and RushHour classes using the Softmax MLP head)

### 2. Edge Latency Benchmarks
- **Model Inference Latency ($t_{inference}$)**: **0.19 ms** (on CPU, extremely edge-compatible)
- **Intrusion Detection Latency ($IDL$)**: **6.39 ms** (includes sFlow push collection and feature pre-processing)
- **End-to-End Mitigation Response ($T_{response}$)**: **9.89 ms** (includes Flask REST API decision, OpenFlow rule push, and OVS switch flow table update)
- **V2X Latency Requirement**: Meets the safety-critical sub-10ms requirement for cooperative ITS networks.
