import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _tmp import TemporaryDirectory  # noqa: E402
from app import state_machine, state_store  # noqa: E402


class TestStateStore(unittest.TestCase):
    def test_persist_and_replay(self):
        with TemporaryDirectory() as d:
            p = os.path.join(d, "state.db")
            s = state_machine.init("s1", goal="导数", concept="导数")
            state_store.create_session("s1", goal="导数", concept="导数", state=s, path=p)
            for ev in ("confirm_goal", "diagnosed", "plan_ready"):
                state_machine.step(s, ev)
                state_store.append_event("s1", ev, {"event": ev}, s, path=p)
            state_machine.step(s, "asked", text="导数定义？")
            state_store.append_event("s1", "asked", {"event": "asked", "text": "导数定义？"}, s, path=p)
            state_machine.step(s, "answer", "correct")
            s.mastery = 0.71
            state_store.append_event("s1", "answer", {"event": "answer", "result": "correct",
                                                      "text": "差商"}, s, path=p)

            loaded, n = state_store.load_state("s1", path=p)
            self.assertEqual(n, 5)
            self.assertEqual(loaded.phase, "ADVANCE")
            self.assertEqual(loaded.question, "导数定义？")
            self.assertAlmostEqual(loaded.mastery, 0.71)
            self.assertTrue(loaded.attempts >= 1)

    def test_reinit_resets_events(self):
        with TemporaryDirectory() as d:
            p = os.path.join(d, "state.db")
            s = state_machine.init("s1")
            state_store.create_session("s1", state=s, path=p)
            state_machine.step(s, "confirm_goal")
            state_store.append_event("s1", "confirm_goal", {"event": "confirm_goal"}, s, path=p)
            self.assertEqual(len(state_store.events("s1", path=p)), 2)
            state_store.create_session("s1", state=state_machine.init("s1"), path=p)
            self.assertEqual(len(state_store.events("s1", path=p)), 1)

    def test_missing_session(self):
        with TemporaryDirectory() as d:
            p = os.path.join(d, "state.db")
            self.assertIsNone(state_store.get_session("nope", path=p))
            self.assertIsNone(state_store.replay("nope", path=p))


if __name__ == "__main__":
    unittest.main()
