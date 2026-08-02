"""Tests for OpenFlow backends and cross-dataset loader protocol."""

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

from sdn_its.controller.of_backend import backend_status, resolve_of_backend
from sdn_its.controller.ovs_manager import OVSManager
from sdn_its.mitigation.containment import FlowRule
from sdn_its.telemetry import TelemetryDataLoader


class TestOfBackend(unittest.TestCase):
    def test_mock_and_queue(self):
        name, cb = resolve_of_backend("mock")
        self.assertEqual(name, "mock")
        rule = FlowRule(
            rule_id="r1",
            dpid="1",
            src_ip="10.0.0.15",
            dst_ip=None,
            action="DROP",
            priority=100,
            created_at=0.0,
            cooldown_seconds=10,
        )
        cb("INSTALL", rule)

        name2, cb2 = resolve_of_backend("queue")
        self.assertEqual(name2, "queue")
        cb2("INSTALL", rule)
        st = backend_status(cb2)
        self.assertGreaterEqual(st["flow_mods"], 1)

    def test_http_backend_resolves(self):
        # Agent may be offline — backend still constructs and reports status shape
        name, cb = resolve_of_backend("http")
        self.assertEqual(name, "http")
        st = backend_status(cb)
        self.assertEqual(st["backend"], "http")
        self.assertIn("connected", st)

    def test_ovs_soft_table(self):
        ovs = OVSManager()
        self.assertIn("s1", ovs.list_bridges())
        self.assertTrue(ovs.apply_flow_mod("s1", {"nw_src": "10.0.0.15"}, ["drop"]))
        self.assertEqual(len(ovs.dump_flows("s1")), 1)


class TestCrossDatasetLoader(unittest.TestCase):
    def test_scaler_fit_on_train_only(self):
        rng = np.random.default_rng(0)
        Xtr = rng.normal(0, 1, size=(80, 10, 10)).astype(np.float32)
        ytr = rng.integers(0, 2, size=(80,), dtype=np.int64)
        Xte = rng.normal(5, 2, size=(40, 10, 10)).astype(np.float32)  # shifted domain
        yte = rng.integers(0, 2, size=(40,), dtype=np.int64)

        with tempfile.TemporaryDirectory() as td:
            tr = os.path.join(td, "train.npz")
            te = os.path.join(td, "test.npz")
            np.savez(tr, X=Xtr, y=ytr)
            np.savez(te, X=Xte, y=yte)
            loader = TelemetryDataLoader(seq_len=10, batch_size=16)
            train_dl, val_dl, test_dl = loader.get_cross_dataset_loaders(tr, te)
            self.assertEqual(len(test_dl.dataset), 40)
            self.assertGreater(len(train_dl.dataset), 0)
            # Holdout batches finite after transform
            bx, _ = next(iter(test_dl))
            self.assertTrue(np.isfinite(bx.numpy()).all())


if __name__ == "__main__":
    unittest.main()
