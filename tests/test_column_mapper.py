import unittest
import sys
import os
import tempfile

import pandas as pd
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(PROJECT_ROOT, "src")
for p in (PROJECT_ROOT, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

from sdn_its.telemetry.column_mapper import (
    canonicalize_dataframe,
    map_label_value,
    normalize_column_name,
)
from sdn_its.telemetry import FEATURE_COLUMNS, TelemetryDataLoader


class TestColumnMapper(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_column_name(" Flow Duration "), "flow duration")
        self.assertEqual(normalize_column_name("Flow_Pkts/s"), "flow pkts/s")

    def test_label_map(self):
        self.assertEqual(map_label_value("Normal"), 0)
        self.assertEqual(map_label_value("BENIGN"), 0)
        self.assertEqual(map_label_value("DDoS"), 1)
        self.assertEqual(map_label_value("Probe"), 2)
        self.assertEqual(map_label_value("RushHour_Burst"), 4)

    def test_insdn_shaped_canonicalize(self):
        df = pd.DataFrame(
            [
                {
                    "Flow Duration": 1_000_000,
                    "Tot Fwd Pkts": 12,
                    "Flow Pkts/s": 40.0,
                    "Flow Byts/s": 8000.0,
                    "Flow IAT Mean": 2000.0,
                    "Flow IAT Std": 100.0,
                    "Pkt Len Mean": 256.0,
                    "SYN Flag Cnt": 1,
                    "Active Mean": 800.0,
                    "Idle Mean": 200.0,
                    "Label": "Normal",
                },
                {
                    "Flow Duration": 500_000,
                    "Tot Fwd Pkts": 900,
                    "Flow Pkts/s": 2000.0,
                    "Flow Byts/s": 400000.0,
                    "Flow IAT Mean": 50.0,
                    "Flow IAT Std": 10.0,
                    "Pkt Len Mean": 64.0,
                    "SYN Flag Cnt": 200,
                    "Active Mean": 900.0,
                    "Idle Mean": 100.0,
                    "Label": "DDoS",
                },
            ]
        )
        # pad to seq requirements later
        for _ in range(20):
            df = pd.concat([df, df.iloc[[0]]], ignore_index=True)

        out, smap = canonicalize_dataframe(df)
        for col in FEATURE_COLUMNS:
            self.assertIn(col, out.columns)
        self.assertEqual(out.loc[0, "label"], 0)
        self.assertEqual(out.loc[1, "label"], 1)
        self.assertIsNotNone(smap["packet_rate"])
        self.assertTrue((out["flow_active_ratio"] >= 0).all())
        self.assertTrue((out["rsu_channel_occupancy"] <= 1.0).all())

    def test_csv_loader_insdn_shaped(self):
        rows = []
        for i in range(40):
            rows.append(
                {
                    "Flow Duration": 1e6,
                    "Flow Pkts/s": 20 + i,
                    "Flow Byts/s": 5000,
                    "Flow IAT Mean": 1000,
                    "Flow IAT Std": 50,
                    "Pkt Len Mean": 200,
                    "Tot Fwd Pkts": 5,
                    "SYN Flag Cnt": 0,
                    "Active Mean": 70,
                    "Idle Mean": 30,
                    "Label": "Normal" if i % 5 else "DDoS",
                }
            )
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "raw.csv")
            pd.DataFrame(rows).to_csv(path, index=False)
            loader = TelemetryDataLoader(seq_len=10, batch_size=8)
            train_dl, val_dl, test_dl = loader.get_csv_loaders(path)
            self.assertGreater(len(train_dl.dataset), 0)
            bx, by = next(iter(train_dl))
            self.assertEqual(tuple(bx.shape[1:]), (10, 10))


if __name__ == "__main__":
    unittest.main()
