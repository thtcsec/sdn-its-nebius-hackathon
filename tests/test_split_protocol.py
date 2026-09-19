"""Tests for split-before-window leakage prevention."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(PROJECT_ROOT, "src")
for p in (PROJECT_ROOT, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

from sdn_its.telemetry.feature_extractor import (
    SPLIT_PROTOCOL,
    TelemetryDataLoader,
    build_windows_from_rows,
    gap_aware_window_index_split,
    row_partition_bounds,
)


class TestSplitBeforeWindow(unittest.TestCase):
    def test_row_partitions_have_gap(self):
        b = row_partition_bounds(1000, 0.7, 0.15, seq_len=10)
        self.assertEqual(b["gap"][0], 9)
        self.assertLessEqual(b["train"][1] + 9, b["val"][0])
        self.assertLessEqual(b["val"][1] + 9, b["test"][0])

    def test_windows_do_not_cross_partitions(self):
        n, f, L = 200, 10, 10
        X = np.arange(n * f, dtype=np.float64).reshape(n, f)
        y = np.zeros(n, dtype=np.int64)
        b = row_partition_bounds(n, 0.7, 0.15, L)
        # Encode row index into feature 0 so we can inspect window row span
        X[:, 0] = np.arange(n, dtype=np.float64)
        for name in ("train", "val", "test"):
            a, c = b[name]
            Xw, _ = build_windows_from_rows(X[a:c], y[a:c], L)
            if len(Xw) == 0:
                continue
            # Absolute row ids in each window
            abs_rows = Xw[:, :, 0]
            self.assertTrue(bool(np.all(abs_rows >= a)))
            self.assertTrue(bool(np.all(abs_rows < c)))

    def test_gap_aware_window_slices(self):
        s = gap_aware_window_index_split(500, 0.7, 0.15, 10)
        self.assertEqual(s["train"].stop + 9, s["val"].start)
        self.assertEqual(s["val"].stop + 9, s["test"].start)

    def test_csv_loader_protocol(self):
        # Build a tiny canonical CSV
        cols = [
            "flow_duration",
            "packet_rate",
            "byte_rate",
            "pkt_iat_mean",
            "pkt_iat_std",
            "packet_len_mean",
            "packet_in_count",
            "tcp_flags_syn_count",
            "flow_active_ratio",
            "rsu_channel_occupancy",
            "label",
        ]
        rng = np.random.default_rng(0)
        rows = 300
        data = {c: rng.normal(size=rows) for c in cols[:-1]}
        data["label"] = rng.integers(0, 5, size=rows)
        import pandas as pd

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "canon.csv")
            pd.DataFrame(data).to_csv(path, index=False)
            loader = TelemetryDataLoader(seq_len=10, batch_size=16)
            tr, va, te = loader.get_csv_loaders(path)
            self.assertEqual(loader.last_split_meta["protocol"], SPLIT_PROTOCOL)
            self.assertGreater(len(tr.dataset), 0)
            self.assertGreater(len(va.dataset), 0)
            self.assertGreater(len(te.dataset), 0)


if __name__ == "__main__":
    unittest.main()
