# Dataset manifests

`datasets.json` lists every dataset the project expects, whether it ships in the
default submission zip, and how to rebuild it.

Large artifacts (`datasets/raw/`, `*.npz`) are **not** in the lean zip — download
via `scripts/download_dataset.py` then `.\reproduce.ps1`.
