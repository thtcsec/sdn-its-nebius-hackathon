# Datasets

Public datasets are **not** committed to git. Download into `datasets/raw/` then prepare.

| Dataset | Purpose | How to use |
|---------|---------|------------|
| **InSDN (real)** | SDN / OpenFlow intrusion flows (~344k rows) | `python scripts/download_dataset.py --name insdn` |
| **CIC-IDS2017** | Cross-dataset holdout (HF, no Kaggle needed) | `python scripts/download_dataset.py --name cicids2017 --prefer hf --prepare` |
| **Synthetic V2X** | RushHour / RSU fault labels | `prepare_data.py --source synthetic` (fallback only) |

## Cross-dataset (InSDN → CIC)

```bash
# Download CIC days (friday/tuesday/…) from Hugging Face — no Kaggle token
python scripts/download_dataset.py --name cicids2017 --prefer hf --prepare
# → datasets/processed/cic_windows.npz

# Score an InSDN-trained checkpoint on CIC holdout (scaler fit on InSDN only)
python scripts/run_cross_dataset.py \
  --train-npz datasets/processed/insdn_windows.npz \
  --test-npz datasets/processed/cic_windows.npz \
  --checkpoint models/checkpoints/tcn_gru_best.pt
# → results/cross_dataset/eval_metrics.json

# Optional: fine-tune on 20% CIC + light CORAL, eval on 80% holdout
python scripts/adapt_to_cic.py --epochs 5 --adapt-ratio 0.2
# → models/checkpoints/tcn_gru_cic_adapted.pt
# → results/cross_dataset/adapted_metrics.json
```

## Recommended research path (not the 800-row demo)

```bash
# 1) Download real InSDN (~141 MB CSV from Hugging Face — no Kaggle token)
pip install -e ".[data]"
python scripts/download_dataset.py --name insdn --prefer hf --prepare
# → datasets/raw/insdn/Dataset.csv
# → datasets/processed/insdn_windows.npz   (~50k windows by default)

# 2) Train on the processed windows (preferred over sample CSV)
python -m sdn_its.ai.train --npz datasets/processed/insdn_windows.npz --epochs 15

# 3) Evaluate + export confusion matrix / metrics JSON
python -m sdn_its.ai.evaluate --npz datasets/processed/insdn_windows.npz

# 4) Ablation: Temporal Transformer vs TCN-GRU
python -m sdn_its.ai.train --arch transformer --npz datasets/processed/insdn_windows.npz --epochs 15
python -m sdn_its.ai.compare --npz datasets/processed/insdn_windows.npz
```

To enlarge the window bank (more of the 344k flows):

```bash
python scripts/prepare_data.py --source insdn --max-rows 200000 --num-samples 5000
```

## Download REAL InSDN (no Kaggle token needed)

```bash
python scripts/download_dataset.py --name insdn --prefer hf --prepare
# → datasets/raw/insdn/Dataset.csv (~141 MB from Hugging Face Sharukesh/INSDN)
# → datasets/sample/canonical_flows.csv + datasets/processed/insdn_windows.npz

python -m sdn_its.ai.train --csv datasets/sample/canonical_flows.csv --epochs 15
```

### Kaggle (optional)

```bash
# https://www.kaggle.com/settings → API → Create New Token → %USERPROFILE%\.kaggle\kaggle.json
pip install kaggle
python scripts/download_dataset.py --name insdn --prefer kaggle --prepare
python scripts/download_dataset.py --name cicids2017 --prefer kaggle --prepare
```

| Mirror | Slug / repo |
|--------|-------------|
| Kaggle InSDN | `phamthaibao/insdn-dataset` |
| Hugging Face InSDN | `Sharukesh/INSDN` (`Dataset.csv`) |
| Kaggle CIC-IDS2017 | `chethuhn/network-intrusion-dataset` |
| Official UCD | https://aseados.ucd.ie/datasets/SDN/ |

**Note:** HF `Sharukesh/INSDN` uses binary `target` (0=normal, 1=attack). Multi-class string `Label` columns appear in original UCD / some Kaggle exports — the mapper accepts both.

## Feature mapping

See `sdn_its.telemetry.column_mapper`. Config: [`configs/dataset.yaml`](../configs/dataset.yaml).

Loader priority in `train` / `evaluate` / `compare`: **NPZ → CSV → synthetic**.
