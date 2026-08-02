"""Unit tests for IoU tracker association."""

from __future__ import annotations

import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(PROJECT_ROOT, "src")
for p in (PROJECT_ROOT, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

from sdn_its.camera.tracker import IoUTracker


class TestIoUTracker(unittest.TestCase):
    def test_same_box_confirms_one_track(self):
        tr = IoUTracker(confirm_hits=2, max_misses=3)
        box = ((10.0, 10.0, 50.0, 50.0), 2)
        t1 = tr.update([box])
        self.assertEqual(len(t1), 0)  # not confirmed yet
        t2 = tr.update([((12.0, 11.0, 52.0, 51.0), 2)])
        self.assertEqual(len(t2), 1)
        tid = t2[0].track_id
        t3 = tr.update([((14.0, 12.0, 54.0, 52.0), 2)])
        self.assertEqual(len(t3), 1)
        self.assertEqual(t3[0].track_id, tid)

    def test_two_objects_two_tracks(self):
        tr = IoUTracker(confirm_hits=1)
        out = tr.update(
            [
                ((10.0, 10.0, 40.0, 40.0), 2),
                ((200.0, 10.0, 240.0, 40.0), 3),
            ]
        )
        self.assertEqual(len(out), 2)


if __name__ == "__main__":
    unittest.main()
