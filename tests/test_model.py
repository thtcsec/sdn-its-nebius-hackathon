import unittest
import torch
import numpy as np
import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(PROJECT_ROOT, "src")
for p in (PROJECT_ROOT, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

from sdn_its.ai import TCNGRUResilienceModel
from sdn_its.telemetry import TelemetryDataLoader, FEATURE_COLUMNS


class TestTCNGRUModel(unittest.TestCase):
    def setUp(self):
        self.model = TCNGRUResilienceModel(num_features=10, num_classes=5)

    def test_forward_pass_dimensions(self):
        dummy_input = torch.randn(8, 10, 10)
        x_hat, logits = self.model(dummy_input)
        self.assertEqual(x_hat.shape, dummy_input.shape)
        self.assertEqual(logits.shape, (8, 5))

    def test_reconstruction_error(self):
        dummy_input = torch.randn(8, 10, 10)
        x_hat, _ = self.model(dummy_input)
        re_err = self.model.compute_reconstruction_error(dummy_input, x_hat)
        self.assertTrue(re_err.item() >= 0.0)

    def test_calibration(self):
        dummy_input = torch.randn(16, 10, 10)
        tau = self.model.calibrate_threshold(dummy_input, k=2.0)
        self.assertTrue(tau > 0.0)
        self.assertEqual(self.model.mu_re.ndim, 0)
        self.assertEqual(self.model.std_re.ndim, 0)

        pred = self.model.predict_anomaly(dummy_input, k=2.0)
        self.assertIn("reconstruction_error", pred)
        self.assertIn("is_anomaly", pred)
        self.assertIn("predicted_class", pred)
        self.assertEqual(len(pred["is_anomaly"]), 16)

    def test_csv_loaders(self):
        temp_csv = "temp_dummy_dataset.csv"
        import pandas as pd

        data = {col: np.random.randn(50) for col in FEATURE_COLUMNS}
        data["label"] = np.random.choice([0, 1], size=50)
        df = pd.DataFrame(data)
        df.to_csv(temp_csv, index=False)

        try:
            loader = TelemetryDataLoader(seq_len=10, batch_size=4)
            train_dl, val_dl, test_dl = loader.get_csv_loaders(temp_csv)

            for bx, by in train_dl:
                self.assertEqual(bx.shape[1], 10)
                self.assertEqual(bx.shape[2], len(FEATURE_COLUMNS))
                self.assertTrue(bx.shape[0] <= 4)
                break
        finally:
            if os.path.exists(temp_csv):
                os.remove(temp_csv)


if __name__ == "__main__":
    unittest.main()
