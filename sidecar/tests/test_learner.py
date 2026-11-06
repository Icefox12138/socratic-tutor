import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _tmp import TemporaryDirectory  # noqa: E402
from app import learner  # noqa: E402


class TestBKT(unittest.TestCase):
    def test_correct_raises_wrong_lowers(self):
        self.assertGreater(learner.bkt_update(0.3, "correct"), 0.3)
        self.assertLess(learner.bkt_update(0.7, "wrong"), 0.7)

    def test_partial_between(self):
        c = learner.bkt_update(0.4, "correct")
        w = learner.bkt_update(0.4, "wrong")
        p = learner.bkt_update(0.4, "partial")
        self.assertGreaterEqual(p, min(c, w))
        self.assertLessEqual(p, max(c, w))

    def test_repeated_correct(self):
        p = 0.3
        for _ in range(3):
            p = learner.bkt_update(p, "correct")
        self.assertGreater(p, 0.85)
        self.assertEqual(learner.level(p), "已掌握")

    def test_reveal_discount(self):
        normal = learner.bkt_update(0.5, "correct", revealed=False)
        revealed = learner.bkt_update(0.5, "correct", revealed=True)
        self.assertAlmostEqual(revealed, normal * 0.5, places=6)

    def test_levels(self):
        self.assertEqual(learner.level(0.2), "未掌握")
        self.assertEqual(learner.level(0.5), "在学")
        self.assertEqual(learner.level(0.8), "已掌握")


class TestStore(unittest.TestCase):
    def test_record_and_get(self):
        with TemporaryDirectory() as d:
            p = os.path.join(d, "state.db")
            r = learner.record("导数", "correct", path=p)
            self.assertGreater(r["after"], r["before"])
            self.assertEqual(learner.get("导数", p)["attempts"], 1)
            learner.record("导数", "wrong", path=p)
            self.assertEqual(learner.get("导数", p)["attempts"], 2)
            self.assertEqual(len(learner.list_all(p)), 1)

    def test_invalid_result(self):
        with TemporaryDirectory() as d:
            p = os.path.join(d, "state.db")
            with self.assertRaises(ValueError):
                learner.record("x", "maybe", path=p)


@unittest.skipUnless(learner._SCHED, "fsrs not installed")
class TestFSRS(unittest.TestCase):
    def test_add_review_due(self):
        with TemporaryDirectory() as d:
            p = os.path.join(d, "state.db")
            card = learner.add_card("lim", "极限", path=p)
            self.assertGreater(card["id"], 0)
            r = learner.review_card(card["id"], "good", path=p)
            self.assertEqual(r["reps"], 1)
            self.assertIsNotNone(r["due"])
            self.assertEqual(learner.due_cards(path=p), [])

    def test_invalid_rating(self):
        with TemporaryDirectory() as d:
            p = os.path.join(d, "state.db")
            card = learner.add_card("lim", "极限", path=p)
            with self.assertRaises(ValueError):
                learner.review_card(card["id"], "perfect", path=p)


if __name__ == "__main__":
    unittest.main()
