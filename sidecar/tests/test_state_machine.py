import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.state_machine import (InvalidTransition, allowed, init, may_reveal,
                               step, summary)  # noqa: E402


class TestStateMachine(unittest.TestCase):
    def setUp(self):
        self.s = init("s1", goal="理解导数", concept="导数")

    def test_align_to_wait(self):
        self.assertEqual(self.s.phase, "ALIGN")
        self.assertEqual(step(self.s, "confirm_goal")["state"]["phase"], "DIAGNOSE")
        self.assertEqual(step(self.s, "diagnosed")["state"]["phase"], "PLAN")
        self.assertEqual(step(self.s, "plan_ready")["state"]["phase"], "ASK")
        self.assertEqual(step(self.s, "asked")["state"]["phase"], "WAIT")

    def test_correct_advance_then_ask(self):
        for e in ("confirm_goal", "diagnosed", "plan_ready", "asked"):
            step(self.s, e)
        r = step(self.s, "answer", "correct")
        self.assertEqual(r["state"]["phase"], "ADVANCE")
        self.assertEqual(r["state"]["correct_streak"], 1)
        self.assertEqual(r["action"]["kind"], "advance")
        r = step(self.s, "next")
        self.assertEqual(r["state"]["phase"], "ASK")

    def test_two_correct_transfer(self):
        for e in ("confirm_goal", "diagnosed", "plan_ready", "asked"):
            step(self.s, e)
        step(self.s, "answer", "correct")
        step(self.s, "next")
        step(self.s, "asked")
        r = step(self.s, "answer", "correct")
        self.assertEqual(r["state"]["phase"], "ADVANCE")
        r = step(self.s, "next")
        self.assertEqual(r["state"]["phase"], "TRANSFER")

    def test_partial_hint_and_retry(self):
        for e in ("confirm_goal", "diagnosed", "plan_ready", "asked"):
            step(self.s, e)
        r = step(self.s, "answer", "partial")
        self.assertEqual(r["state"]["phase"], "HINT")
        self.assertEqual(r["state"]["hint_level"], 1)
        self.assertEqual(r["state"]["attempts"], 1)
        self.assertEqual(step(self.s, "asked")["state"]["phase"], "WAIT")
        r = step(self.s, "answer", "wrong")
        self.assertEqual(r["state"]["hint_level"], 2)
        self.assertEqual(r["state"]["attempts"], 2)
        self.assertEqual(r["state"]["frustration"], 1)

    def test_hint_request_and_reveal_policy(self):
        self.s.phase = "WAIT"
        r = step(self.s, "hint_request")
        self.assertEqual(r["state"]["phase"], "HINT")
        self.assertEqual(r["state"]["hint_level"], 1)
        self.assertFalse(may_reveal(self.s))
        self.s.attempts = 2
        self.s.hint_level = 3
        self.assertTrue(may_reveal(self.s))
        r = step(self.s, "hint_request")
        self.assertEqual(r["state"]["hint_level"], 5)
        self.assertTrue(r["state"]["revealed"])
        self.assertEqual(r["action"]["kind"], "reveal")

    def test_stop_terminal(self):
        r = step(self.s, "stop")
        self.assertEqual(r["state"]["phase"], "SUMMARY")
        self.assertEqual(r["action"]["kind"], "summary")
        with self.assertRaises(InvalidTransition):
            step(self.s, "confirm_goal")

    def test_invalid_event(self):
        with self.assertRaises(InvalidTransition):
            step(self.s, "answer", "correct")
        with self.assertRaises(InvalidTransition):
            step(self.s, "confirm_goal")
            step(self.s, "answer", "correct")

    def test_summary_contains_fields(self):
        self.s.phase = "WAIT"
        self.s.attempts = 2
        self.s.hint_level = 2
        t = summary(self.s)
        for k in ("阶段=WAIT", "概念=导数", "尝试=2", "L2", "已揭示=否"):
            self.assertIn(k, t)

    # ── curriculum hooks: LEARN / REVIEW (opt-in, old flow unchanged) ─────────

    def test_learn_pass_is_opt_in(self):
        s = init("s2", goal="g", concept="c", learn=True)
        step(s, "confirm_goal")
        r = step(s, "diagnosed")
        self.assertEqual(r["state"]["phase"], "LEARN")
        self.assertEqual(r["action"]["kind"], "learn")
        self.assertIn("worked example", r["action"]["instruction"])
        r = step(s, "learn_done")
        self.assertEqual(r["state"]["phase"], "PLAN")
        self.assertEqual(step(s, "plan_ready")["state"]["phase"], "ASK")

    def test_learn_phase_rejects_answer_and_review_done(self):
        s = init("s4", goal="g", concept="c", learn=True)
        step(s, "confirm_goal")
        step(s, "diagnosed")
        with self.assertRaises(InvalidTransition):
            step(s, "answer", "correct")
        with self.assertRaises(InvalidTransition):
            step(s, "review_done")

    def test_review_opens_the_session(self):
        s = init("s3", goal="g", concept="c", review=True)
        self.assertEqual(s.phase, "REVIEW")
        self.assertIn("review_done", allowed(s))
        r = step(s, "review_done")
        self.assertEqual(r["state"]["phase"], "DIAGNOSE")

    def test_summary_shows_the_lesson(self):
        s = init("s5", goal="g", concept="c", lesson="demo-1")
        self.assertIn("课=demo-1", summary(s))


if __name__ == "__main__":
    unittest.main()
