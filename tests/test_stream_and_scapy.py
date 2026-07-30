import os
import sys
import unittest

import torch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(PROJECT_ROOT, "src")
for p in (PROJECT_ROOT, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

from sdn_its.simulation.scapy_traffic import ScapyTelemetryInjector
from sdn_its.telemetry import StreamingTelemetryBuffer


class TestStreamBufferAndScapy(unittest.TestCase):
    def test_stream_buffer_push(self):
        buf = StreamingTelemetryBuffer(seq_len=10, num_features=10)
        self.assertTrue(buf.is_full())

        sample_feat = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        tensor_out = buf.push(sample_feat)

        self.assertEqual(tensor_out.shape, (1, 10, 10))
        self.assertTrue(torch.is_tensor(tensor_out))

    def test_scapy_injector_mock(self):
        injector = ScapyTelemetryInjector(controller_url="http://127.0.0.1:9999")
        injector.generate_ddos_flood(count=10, src_ip="10.0.0.15")
        self.assertEqual(injector.packet_count, 10)


if __name__ == "__main__":
    unittest.main()
