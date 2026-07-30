# Datasets

Public datasets are **not** committed to git. Download into `datasets/raw/` then prepare.

| Dataset | Purpose | How to use |
|---------|---------|------------|
| **InSDN (real)** | SDN / OpenFlow intrusion flows | `python scripts/download_dataset.py --name insdn` |
| **CSE-CIC-IDS2017** | General attacks (Kaggle) | needs `~/.kaggle/kaggle.json` → `--name cicids2017 --prefer kaggle` |
| **Synthetic V2X** | RushHour / RSU fault labels | `prepare_data.py --source synthetic` (fallback only) |

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
