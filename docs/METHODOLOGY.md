# Methodology notes (audit response)

Honest answers to the pre-submit methodology questions. Canonical code paths:
`src/sdn_its/telemetry/feature_extractor.py`, `scripts/prepare_data.py`,
`src/sdn_its/ai/train.py`, `src/sdn_its/ai/evaluate.py`.

## 1. Sliding windows & leakage prevention

**Protocol id:** `rows_before_window_v1`

1. Shuffle raw flow rows (`seed=42` by default in `prepare_data`).
2. Partition **rows** into train / val / test with a **gap of `(seq_len - 1)` rows** between partitions so no window can span two splits.
3. Build sliding windows (`L=10`, stride `1`) **inside each partition only**.
4. Fit `StandardScaler` on **training rows/windows only**; transform val/test.

New NPZs write `X_train/y_train/...` plus `protocol`. Legacy NPZs with only `X/y` use a **gap-aware window-index split** + train-only scaler and print a re-prepare warning.

> Tracked Acc/F1/AUC under `artifacts/results/` were produced **before** this protocol landed. Cite them as preliminary until `prepare → train → evaluate → sync_artifacts` is re-run.

## 2. Cross-dataset name: CICIDS2017 (not CSE-CIC-IDS2018)

Experiments, README, and `scripts/download_dataset.py --name cicids2017` use **CIC-IDS2017** (UNB / HF `bvk/CICIDS-2017`).  
Proposal text must say **CICIDS2017**, not CSE-CIC-IDS2018. Cite Sharafaldin et al. CIC-IDS2017 (ICCIS 2018 / UNB page) consistently.

## 3. What Table “96.2% / 97.7% / 0.977” actually is

These are **`cls_binary_*` metrics**, not 5-class macro scores:

| Field | Definition |
|-------|------------|
| `cls_binary_precision/recall/f1` | Binary Normal vs Anomaly where prediction = `(argmax class > 0)`; sklearn `average="binary"` |
| `roc_auc` | Binary ROC-AUC with score `sum(P(class ≠ Normal))` |
| `macro_*` / `weighted_*` | Exported separately by `evaluate.py` |
| `macro_roc_auc_ovr` | sklearn `multi_class="ovr", average="macro"` |

Do **not** label the binary numbers as “macro multiclass F1/AUC”.

## 4. Loss & threshold defaults

$$
L = L_{\mathrm{MSE}}(\hat x, x \mid y=\mathrm{Normal}) + \alpha\, L_{\mathrm{CE}}(\hat y, y)
$$

| Parameter | Default | Notes |
|-----------|---------|-------|
| `alpha` | **1.0** | CLI `--alpha` |
| `k` in \(\tau=\mu_{RE}+k\sigma_{RE}\) | **2.0** | CLI `--k_sigma`; calibrated on **validation normals** at checkpoint save |
| Online τ adaptation | **Off** for reported offline eval | Console may adapt live (`adapt_tau`); not used in `evaluate.py` metrics |
| Seed | **42** | `train.py --seed` |

## 5. RQ2 wording (recommended)

> Can a lightweight TCN-GRU model satisfy prototype edge-level latency and memory constraints while maintaining **useful in-domain** anomaly-detection performance?

Avoid “competitive” until a full multi-seed ablation table is regenerated.

## 6. Experiment A sample size

`ping_count=20` demonstrates install → suppress → DELETE → restore. Keep claims as **ICMP delivery ratios**, not PacketIn/s or city-scale PDR.
