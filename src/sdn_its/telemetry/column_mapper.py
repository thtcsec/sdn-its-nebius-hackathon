"""Map InSDN / CICFlowMeter / CIC-IDS columns onto the 10-feature SDN-ITS schema."""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from .schema import FEATURE_COLUMNS, LABEL_MAPPING

# Canonical feature <- possible source column names (normalized)
FEATURE_ALIASES: Dict[str, List[str]] = {
    "flow_duration": [
        "flow_duration",
        "flow duration",
        "flowduration",
        "duration",
    ],
    "packet_rate": [
        "packet_rate",
        "flow pkts/s",
        "flow packets/s",
        "flow pkt/s",
        "fwd pkts/s",
        "fwd packets/s",
    ],
    "byte_rate": [
        "byte_rate",
        "flow byts/s",
        "flow bytes/s",
        "flow byt/s",
        "fwd byts/s",
        "fwd bytes/s",
    ],
    "pkt_iat_mean": [
        "pkt_iat_mean",
        "flow iat mean",
        "fwd iat mean",
        "iat mean",
    ],
    "pkt_iat_std": [
        "pkt_iat_std",
        "flow iat std",
        "fwd iat std",
        "iat std",
    ],
    "packet_len_mean": [
        "packet_len_mean",
        "pkt len mean",
        "packet length mean",
        "pkt size avg",
        "average packet size",
        "avg packet size",
    ],
    "packet_in_count": [
        "packet_in_count",
        "packet in count",
        "packet_in",
        # SDN proxy when OpenFlow counters absent (InSDN paper Table 7 style)
        "tot fwd pkts",
        "total fwd packets",
        "fwd act data pkts",
    ],
    "tcp_flags_syn_count": [
        "tcp_flags_syn_count",
        "syn flag cnt",
        "syn flag count",
        "syn flags",
    ],
    "flow_active_ratio": [
        "flow_active_ratio",
        "active/idle ratio",
    ],
    "rsu_channel_occupancy": [
        "rsu_channel_occupancy",
        "channel occupancy",
        "rsu occupancy",
    ],
}

LABEL_COLUMN_ALIASES = ["label", "class", "attack", "attack_type", "category", "target", "y"]

# InSDN / CIC string labels -> our 5-class taxonomy
LABEL_ALIASES: Dict[str, int] = {
    "normal": 0,
    "benign": 0,
    "0": 0,
    "ddos": 1,
    "ddos_packetin_flood": 1,
    "ddos attack": 1,
    "dos": 1,
    "dos slowloris": 1,
    "dos slowhttptest": 1,
    "dos hulk": 1,
    "dos goldeneye": 1,
    "loft": 2,
    "loft_lowrate_attack": 2,
    "probe": 2,
    "portscan": 2,
    "port scan": 2,
    "infiltration": 2,
    "bfa": 2,
    "bruteforce": 2,
    "brute force": 2,
    "web-attack": 2,
    "web attack": 2,
    "webattack": 2,
    "bot": 1,
    "botnet": 1,
    "u2r": 3,
    "exploitation": 3,
    "exploit": 3,
    "fault": 3,
    "rsu_link_fault": 3,
    "rushhour": 4,
    "rush_hour": 4,
    "rushhour_burst": 4,
    "rush-hour": 4,
}


def normalize_column_name(name: str) -> str:
    """Lowercase, strip, collapse punctuation/whitespace for fuzzy matching."""
    s = str(name).strip().lower()
    s = s.replace("\\", "/")
    s = re.sub(r"[\s_\-]+", " ", s)
    s = re.sub(r"[^\w\s/\.]+", "", s)
    return s.strip()


def _build_normalized_lookup(columns: Iterable[str]) -> Dict[str, str]:
    return {normalize_column_name(c): c for c in columns}


def resolve_column(columns: Iterable[str], aliases: List[str]) -> Optional[str]:
    lookup = _build_normalized_lookup(columns)
    for alias in aliases:
        key = normalize_column_name(alias)
        if key in lookup:
            return lookup[key]
    return None


def map_label_value(value) -> int:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return 0
    if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
        iv = int(value)
        return iv if iv in LABEL_MAPPING else (0 if iv == 0 else 1)
    key = normalize_column_name(str(value)).replace(" ", "_").replace("/", "_")
    key_space = normalize_column_name(str(value))
    if key in LABEL_ALIASES:
        return LABEL_ALIASES[key]
    if key_space in LABEL_ALIASES:
        return LABEL_ALIASES[key_space]
    # Partial contains
    for alias, code in LABEL_ALIASES.items():
        if alias in key_space or alias in key:
            return code
    return 1  # unknown attack-like traffic -> anomaly class


def _series_or_default(df: pd.DataFrame, col: Optional[str], default: float = 0.0) -> pd.Series:
    if col is None:
        return pd.Series(np.full(len(df), default, dtype=np.float64), index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(default)


def canonicalize_dataframe(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Optional[str]]]:
    """
    Convert a raw InSDN/CIC/canonical CSV into FEATURE_COLUMNS + label.

    Returns (canonical_df, source_map) where source_map[feature] = original column or None.
    """
    if df is None or len(df) == 0:
        raise ValueError("Empty dataframe — cannot canonicalize")

    # Strip BOM / whitespace from headers
    df = df.copy()
    df.columns = [str(c).strip().lstrip("\ufeff") for c in df.columns]

    source_map: Dict[str, Optional[str]] = {}
    out = pd.DataFrame(index=df.index)

    for feature, aliases in FEATURE_ALIASES.items():
        src = resolve_column(df.columns, aliases)
        source_map[feature] = src
        out[feature] = _series_or_default(df, src, 0.0)

    # Derive packet_rate from Tot Fwd Pkts / duration if still zero-ish and totals exist
    tot_fwd = resolve_column(df.columns, ["tot fwd pkts", "total fwd packets", "total fwd pkts"])
    dur_col = source_map.get("flow_duration")
    if tot_fwd and (out["packet_rate"].abs().sum() == 0 or source_map["packet_rate"] is None):
        dur = _series_or_default(df, dur_col, 1.0).clip(lower=1e-3)
        # InSDN Flow Duration is microseconds; convert to seconds for rate
        dur_s = dur / 1e6 if dur.median() > 1e3 else dur
        out["packet_rate"] = _series_or_default(df, tot_fwd) / dur_s.replace(0, np.nan)
        out["packet_rate"] = out["packet_rate"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        source_map["packet_rate"] = source_map["packet_rate"] or f"derived:{tot_fwd}/duration"

    # flow_active_ratio from Active Mean / (Active Mean + Idle Mean)
    if source_map["flow_active_ratio"] is None:
        active = resolve_column(df.columns, ["active mean", "active mean", "fwd active mean"])
        idle = resolve_column(df.columns, ["idle mean", "idle mean", "fwd idle mean"])
        if active or idle:
            a = _series_or_default(df, active, 0.0)
            i = _series_or_default(df, idle, 0.0)
            denom = (a + i).replace(0, np.nan)
            out["flow_active_ratio"] = (a / denom).fillna(0.5).clip(0.0, 1.0)
            source_map["flow_active_ratio"] = "derived:active/(active+idle)"

    # rsu_channel_occupancy proxy from normalized packet rate when ITS column absent
    if source_map["rsu_channel_occupancy"] is None:
        pr = out["packet_rate"].astype(float)
        p99 = np.nanpercentile(pr.replace([np.inf, -np.inf], np.nan).dropna(), 99) if pr.notna().any() else 1.0
        p99 = max(float(p99), 1.0)
        out["rsu_channel_occupancy"] = (pr / p99).clip(0.0, 1.0)
        source_map["rsu_channel_occupancy"] = "derived:packet_rate/p99"

    # Flow duration: if clearly microseconds, convert to seconds for model stability
    if out["flow_duration"].median() > 1e4:
        out["flow_duration"] = out["flow_duration"] / 1e6

    # IAT often in microseconds in CICFlowMeter — convert to ms-ish scale if huge
    for iat_col in ("pkt_iat_mean", "pkt_iat_std"):
        if out[iat_col].median() > 1e4:
            out[iat_col] = out[iat_col] / 1e3

    label_src = resolve_column(df.columns, LABEL_COLUMN_ALIASES)
    source_map["label"] = label_src
    if label_src is None:
        out["label"] = 0
    else:
        out["label"] = df[label_src].map(map_label_value).astype(np.int64)

    # Sanitize
    out[FEATURE_COLUMNS] = out[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    out["label"] = out["label"].astype(np.int64)
    return out[FEATURE_COLUMNS + ["label"]], source_map


def load_and_canonicalize_csv(path: str) -> Tuple[pd.DataFrame, Dict[str, Optional[str]]]:
    df = pd.read_csv(path, low_memory=False)
    return canonicalize_dataframe(df)
