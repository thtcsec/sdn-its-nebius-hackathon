#!/usr/bin/env python
"""Prepare datasets: map InSDN/CIC raw CSVs or generate synthetic V2X samples."""

from __future__ import annotations

import argparse
from pathlib import Path

import _bootstrap  # noqa: F401
import numpy as np
import pandas as pd

from sdn_its.telemetry.column_mapper import canonicalize_dataframe
from sdn_its.telemetry.feature_extractor import FEATURE_COLUMNS, generate_synthetic_telemetry
from sdn_its.utils.config import load_config
from sdn_its.utils.paths import PROJECT_ROOT, ensure_dir


def _write_windows_npz(
    canonical: pd.DataFrame,
    seq_len: int,
    out_path: Path,
    *,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    seed: int = 42,
):
    """Split raw rows first, then build windows inside each partition (no overlap leakage)."""
    from sdn_its.telemetry.feature_extractor import (
        SPLIT_PROTOCOL,
        build_windows_from_rows,
        row_partition_bounds,
    )

    X = canonical[FEATURE_COLUMNS].values.astype(np.float32)
    y = canonical["label"].values.astype(np.int64)
    if len(X) < seq_len * 3:
        raise ValueError(f"Need enough rows for split-before-window, got {len(X)}")

    bounds = row_partition_bounds(len(X), train_ratio, val_ratio, seq_len)
    parts = {}
    for name in ("train", "val", "test"):
        a, b = bounds[name]
        Xw, yw = build_windows_from_rows(X[a:b], y[a:b], seq_len)
        parts[name] = (Xw, yw)
        if len(Xw) == 0:
            raise ValueError(f"Partition {name} produced 0 windows (rows {a}:{b})")

    np.savez_compressed(
        out_path,
        X_train=parts["train"][0],
        y_train=parts["train"][1],
        X_val=parts["val"][0],
        y_val=parts["val"][1],
        X_test=parts["test"][0],
        y_test=parts["test"][1],
        # Legacy concat for older scripts that only read X/y (loader still gap-splits)
        X=np.concatenate([parts["train"][0], parts["val"][0], parts["test"][0]], axis=0),
        y=np.concatenate([parts["train"][1], parts["val"][1], parts["test"][1]], axis=0),
        protocol=SPLIT_PROTOCOL,
        seq_len=np.asarray(seq_len),
        seed=np.asarray(seed),
        train_ratio=np.asarray(train_ratio),
        val_ratio=np.asarray(val_ratio),
        gap_rows=np.asarray(bounds["gap"][0]),
        row_bounds_train=np.asarray(bounds["train"]),
        row_bounds_val=np.asarray(bounds["val"]),
        row_bounds_test=np.asarray(bounds["test"]),
    )
    total = sum(len(parts[n][0]) for n in ("train", "val", "test"))
    return total, {n: int(len(parts[n][0])) for n in ("train", "val", "test")}


def _generate_insdn_shaped_sample(n: int = 400, seed: int = 42) -> pd.DataFrame:
    """CICFlowMeter-like columns so mapper can be tested without downloading InSDN."""
    rng = np.random.default_rng(seed)
    labels = rng.choice(
        ["Normal", "DDoS", "Probe", "DoS", "BFA", "BOTNET"],
        size=n,
        p=[0.55, 0.15, 0.10, 0.10, 0.05, 0.05],
    )
    rows = []
    for lab in labels:
        dur_us = float(rng.uniform(1e4, 5e6))
        tot_fwd = int(rng.integers(1, 40))
        if lab == "DDoS":
            tot_fwd = int(rng.integers(200, 2000))
            flow_pkts = float(rng.uniform(800, 5000))
            syn = int(rng.integers(50, 400))
            iat = float(rng.uniform(10, 200))
        elif lab in ("Probe", "BFA"):
            flow_pkts = float(rng.uniform(5, 40))
            syn = int(rng.integers(5, 30))
            iat = float(rng.uniform(5e4, 5e5))
        elif lab == "DoS":
            flow_pkts = float(rng.uniform(100, 800))
            syn = int(rng.integers(20, 100))
            iat = float(rng.uniform(100, 2000))
        else:
            flow_pkts = float(rng.uniform(10, 80))
            syn = int(rng.integers(0, 5))
            iat = float(rng.uniform(1e3, 2e4))

        active = float(rng.uniform(1e3, 1e5))
        idle = float(rng.uniform(1e3, 1e5))
        rows.append(
            {
                "Flow Duration": dur_us,
                "Tot Fwd Pkts": tot_fwd,
                "Flow Pkts/s": flow_pkts,
                "Flow Byts/s": flow_pkts * float(rng.uniform(200, 1200)),
                "Flow IAT Mean": iat,
                "Flow IAT Std": iat * float(rng.uniform(0.1, 0.5)),
                "Pkt Len Mean": float(rng.uniform(60, 1200)),
                "SYN Flag Cnt": syn,
                "Active Mean": active,
                "Idle Mean": idle,
                "Label": lab,
            }
        )
    return pd.DataFrame(rows)


def _collect_raw_csvs(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    return sorted([p for p in folder.rglob("*.csv") if p.is_file()])


def _stratified_sample(df: pd.DataFrame, label_col: str, n: int, seed: int) -> pd.DataFrame:
    """Sample ~n rows keeping class proportions."""
    counts = df[label_col].value_counts()
    parts = []
    assigned = 0
    classes = list(counts.index)
    for i, cls in enumerate(classes):
        g = df[df[label_col] == cls]
        if i == len(classes) - 1:
            k = min(len(g), n - assigned)
        else:
            k = max(1, int(round(n * (len(g) / len(df)))))
            k = min(k, len(g), n - assigned - (len(classes) - i - 1))
        parts.append(g.sample(n=k, random_state=seed))
        assigned += k
    return pd.concat(parts, ignore_index=True).sample(frac=1.0, random_state=seed).reset_index(drop=True)


def _load_raw_folder(folder: Path, max_rows: int | None, seed: int = 42) -> pd.DataFrame:
    files = _collect_raw_csvs(folder)
    if not files:
        raise FileNotFoundError(f"No CSV files under {folder}")
    frames = []
    for f in files:
        chunk = pd.read_csv(f, low_memory=False)
        frames.append(chunk)
        print(f"[+] Loaded {f.relative_to(PROJECT_ROOT)} rows={len(chunk)}")
    raw = pd.concat(frames, ignore_index=True)
    if max_rows is not None and len(raw) > max_rows:
        label_col = None
        for c in raw.columns:
            if str(c).strip().lower() in {"label", "target", "class", "attack"}:
                label_col = c
                break
        if label_col is not None:
            raw = _stratified_sample(raw, label_col, max_rows, seed)
        else:
            raw = raw.sample(n=max_rows, random_state=seed).reset_index(drop=True)
        print(f"[*] Subsampled to {len(raw)} rows (seed={seed})")
        if label_col is not None:
            print(f"[*] Class balance: {raw[label_col].value_counts().to_dict()}")
    return raw


def main():
    parser = argparse.ArgumentParser(description="Prepare SDN-ITS datasets")
    parser.add_argument(
        "--source",
        choices=["auto", "synthetic", "insdn", "cic"],
        default="auto",
        help="auto: use raw InSDN/CIC if present else synthetic",
    )
    parser.add_argument("--num-samples", type=int, default=800)
    parser.add_argument("--seq-len", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-rows", type=int, default=50000, help="Cap rows from raw CSVs")
    args = parser.parse_args()

    cfg = {}
    try:
        cfg = load_config("dataset")
    except Exception:
        pass

    paths = cfg.get("paths", {})
    sample_dir = ensure_dir(PROJECT_ROOT / "datasets" / "sample")
    processed_dir = ensure_dir(PROJECT_ROOT / "datasets" / "processed")
    raw_insdn = PROJECT_ROOT / paths.get("raw_insdn", "datasets/raw/insdn")
    raw_cic = PROJECT_ROOT / paths.get("raw_cic", "datasets/raw/cicids2017")

    source = args.source
    if source == "auto":
        if _collect_raw_csvs(raw_insdn):
            source = "insdn"
        elif _collect_raw_csvs(raw_cic):
            source = "cic"
        else:
            source = "synthetic"
        print(f"[*] auto source -> {source}")

    # Always refresh InSDN-shaped fixture for mapper demos / CI
    insdn_shaped = _generate_insdn_shaped_sample(n=min(args.num_samples, 500), seed=args.seed)
    shaped_path = sample_dir / "insdn_shaped_sample.csv"
    insdn_shaped.to_csv(shaped_path, index=False)
    print(f"[+] Wrote {shaped_path.relative_to(PROJECT_ROOT)} ({len(insdn_shaped)} rows)")

    if source == "synthetic":
        X, y = generate_synthetic_telemetry(
            num_samples=args.num_samples, seq_len=1, seed=args.seed
        )
        # seq_len=1 gives flat feature rows for CSV; rebuild windows later
        flat = X[:, 0, :]
        canonical = pd.DataFrame(flat, columns=FEATURE_COLUMNS)
        canonical["label"] = y
        # Also validate mapper on shaped sample
        mapped_shaped, smap = canonicalize_dataframe(insdn_shaped)
        print(f"[*] Mapper check on InSDN-shaped sample: label dist={mapped_shaped['label'].value_counts().to_dict()}")
        print(f"[*] Source map: { {k: v for k, v in smap.items() if k != 'label'} }")
    elif source == "insdn":
        raw = _load_raw_folder(raw_insdn, args.max_rows, seed=args.seed)
        canonical, smap = canonicalize_dataframe(raw)
        print(f"[*] InSDN source map: {smap}")
    else:  # cic
        raw = _load_raw_folder(raw_cic, args.max_rows, seed=args.seed)
        canonical, smap = canonicalize_dataframe(raw)
        print(f"[*] CIC source map: {smap}")

    # Drop extreme NaN rows already filled; shuffle for better splits
    canonical = canonical.sample(frac=1.0, random_state=args.seed).reset_index(drop=True)

    canon_path = sample_dir / "canonical_flows.csv"
    # Keep sample modest for git; full processed goes to npz
    sample_n = min(len(canonical), max(400, args.num_samples))
    canonical.head(sample_n).to_csv(canon_path, index=False)
    print(f"[+] Wrote {canon_path.relative_to(PROJECT_ROOT)} ({sample_n} rows)")

    # Full processed windows (from entire canonical set, capped)
    full = canonical.head(min(len(canonical), args.max_rows))
    npz_name = {
        "synthetic": "synthetic_windows.npz",
        "insdn": "insdn_windows.npz",
        "cic": "cic_windows.npz",
    }[source]
    n_win, split_counts = _write_windows_npz(
        full, args.seq_len, processed_dir / npz_name, seed=args.seed
    )
    print(f"[+] Wrote datasets/processed/{npz_name} windows={n_win} split={split_counts}")

    # Manifest
    manifest = processed_dir / "last_prepare.json"
    import json

    from sdn_its.telemetry.feature_extractor import SPLIT_PROTOCOL

    manifest.write_text(
        json.dumps(
            {
                "source": source,
                "rows": int(len(full)),
                "windows": int(n_win),
                "split_counts": split_counts,
                "seq_len": args.seq_len,
                "seed": args.seed,
                "split_protocol": SPLIT_PROTOCOL,
                "label_counts": {str(k): int(v) for k, v in full["label"].value_counts().items()},
                "canonical_sample": str(canon_path.relative_to(PROJECT_ROOT)),
                "note": (
                    "Raw rows partitioned train/val/test before sliding windows; "
                    "gap=(seq_len-1) rows between partitions; scaler fit at train time on train only."
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[+] Wrote {manifest.relative_to(PROJECT_ROOT)}")
    print("[OK] prepare_data complete")


if __name__ == "__main__":
    main()
