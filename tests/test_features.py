import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(PROJECT_ROOT, "src")
for p in (PROJECT_ROOT, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

from sdn_its.telemetry import FEATURE_COLUMNS, LABEL_MAPPING, generate_synthetic_telemetry
from sdn_its.telemetry.normalizer import FeatureNormalizer


class TestFeatures(unittest.TestCase):
    def test_feature_schema(self):
        self.assertEqual(len(FEATURE_COLUMNS), 10)
        self.assertIn(0, LABEL_MAPPING)

    def test_synthetic_and_normalizer(self):
        X, y = generate_synthetic_telemetry(num_samples=32, seq_len=10)
        self.assertEqual(X.shape, (32, 10, 10))
        self.assertEqual(y.shape, (32,))
        norm = FeatureNormalizer()
        Xs = norm.fit_transform(X)
        self.assertEqual(Xs.shape, X.shape)


if __name__ == "__main__":
    unittest.main()
