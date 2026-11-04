import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import toc  # noqa: E402


class TestCleanVolumes(unittest.TestCase):
    def test_single_page_noise_is_dropped(self):
        vols = {10: 13, 11: None, 12: 28, 13: None,
                20: 1, 21: 1, 22: 1, 23: 1, 24: 1}
        clean = toc.clean_volumes(vols, min_run=5)
        self.assertEqual(set(clean.values()), {1})
        self.assertNotIn(10, clean)

    def test_real_runs_survive(self):
        vols = {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 2, 7: 2, 8: 2, 9: 2, 10: 2}
        clean = toc.clean_volumes(vols, min_run=5)
        chapters = toc.build_from_volumes(clean)
        self.assertEqual([c["volume"] for c in chapters], [1, 2])
        self.assertEqual(chapters[0]["page_end"], 5)
