import unittest
import torch
import numpy as np
import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from models.tcn_gru import TCNGRUResilienceModel
from data.data_loader import TelemetryDataLoader

class TestTCNGRUModel(unittest.TestCase):
    def setUp(self):
        self.model = TCNGRUResilienceModel(num_features=10, num_classes=5)
        
    def test_forward_pass_dimensions(self):
        dummy_input = torch.randn(8, 10, 10)  # batch=8, seq=10, features=10
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
        
        # Test anomaly prediction structure
        pred = self.model.predict_anomaly(dummy_input, k=2.0)
        self.assertIn("reconstruction_error", pred)
        self.assertIn("is_anomaly", pred)
        self.assertIn("predicted_class", pred)
        self.assertEqual(len(pred["is_anomaly"]), 16)

if __name__ == "__main__":
    unittest.main()
