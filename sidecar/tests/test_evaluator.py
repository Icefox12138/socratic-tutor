import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import critic, evaluations, evaluator  # noqa: E402
from app.state_machine import init, step  # noqa: E402


class TestEvaluator(unittest.TestCase):
    def test_expected_exact(self):
        ev = evaluator.evaluate("2+2?", "4", expected="4", use_llm=False)
        self.assertEqual(ev["result"], "correct")
        self.assertEqual(ev["source"], "rule")

    def test_expected_numeric(self):
        ev = evaluator.evaluate("极限?", "2.0", expected="2", use_llm=False)
        self.assertEqual(ev["result"], "correct")

    def test_short_prefix_not_correct(self):
        ev = evaluator.evaluate("导数定义?", "差商", expected="差商的极限", use_llm=False)
        self.assertNotEqual(ev["result"], "correct")

    def test_rubric_full_partial_wrong(self):
        q = "导数定义"
        r = "差商,极限"
        self.assertEqual(evaluator.evaluate(q, "差商的极限", rubric=r, use_llm=False)["result"], "correct")
        self.assertEqual(evaluator.evaluate(q, "差商", rubric=r, use_llm=False)["result"], "partial")
        self.assertEqual(evaluator.evaluate(q, "不知道", rubric=r, use_llm=False)["result"], "wrong")

    def test_empty_is_wrong(self):
        ev = evaluator.evaluate("q", "  ", use_llm=False)
        self.assertEqual(ev["result"], "wrong")
        self.assertIn("空回答", ev["misconceptions"])

    def test_llm_disabled_fallback(self):
        ev = evaluator.evaluate("开放题", "某个回答", use_llm=False)
        self.assertEqual(ev["result"], "partial")
        self.assertEqual(ev["source"], "fallback")

    def test_bad_json(self):
        with self.assertRaises(ValueError):
            evaluator._parse("not json")

    def test_save_and_list(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "state.db")
            ev = evaluator.evaluate("q", "4", expected="4", use_llm=False)
            eid = evaluations.save("s1", "q", "4", ev, path=p)
            self.assertGreater(eid, 0)
            rows = evaluations.list_for("s1", path=p)
            self.assertEqual(rows[0]["result"], "correct")
            self.assertEqual(rows[0]["answer"], "4")


class TestCritic(unittest.TestCase):
    def test_leak(self):
        r = critic.check("答案是 2", hint_level=2)
        self.assertIn("leak", r["flags"])
        self.assertFalse(r["ok"])

    def test_multi_question(self):
        r = critic.check("这是什么？为什么？", hint_level=1)
        self.assertIn("multi_question", r["flags"])
        self.assertEqual(r["rewrite"]["text"], "这是什么？")
        self.assertTrue(r["rewrite"]["changed"])

    def test_rewrite_no_question(self):
        r = critic.rewrite_one_question("先看定义。")
        self.assertFalse(r["changed"])

    def test_rewrite_single_question_unchanged(self):
        r = critic.rewrite_one_question("它是什么？")
        self.assertFalse(r["changed"])

    def test_rewrite_keeps_hint_after_second_question(self):
        r = critic.rewrite_one_question("问题一？问题二？提示：先看定义。")
        self.assertEqual(r["text"], "问题一？提示：先看定义。")
        self.assertTrue(r["changed"])

    def test_empty_hint(self):
        r = critic.check("再想想", hint_level=2)
        self.assertIn("empty_hint", r["flags"])

    def test_uncited(self):
        r = critic.check("根据研究，答案是这样。", hint_level=2, has_citation=False)
        self.assertIn("uncited_claim", r["flags"])
        self.assertIn("citation_rewrite", r)
        self.assertIn("未核验", r["citation_rewrite"]["text"])

    def test_cited_unchanged(self):
        r = critic.check("根据研究，答案是 2（p.12）。", hint_level=2, has_citation=True)
        self.assertNotIn("uncited_claim", r["flags"])

    def test_citation_modes(self):
        t = "根据定理，A 成立。你能复述吗？"
        soft = critic.soften_uncited(t, "soften")
        self.assertIn("未核验", soft["text"])
        self.assertNotIn("根据定理", soft["text"])
        mark = critic.soften_uncited(t, "mark")
        self.assertIn("未引用", mark["text"])
        self.assertIn("根据定理", mark["text"])
        off = critic.soften_uncited(t, "off")
        self.assertFalse(off["changed"])

    def test_leak_modes(self):
        t = "答案是 2。"
        self.assertIn("不揭示", critic.soften_leak(t, 2)["text"])
        self.assertFalse(critic.soften_leak(t, 4)["changed"])
        self.assertIn("未揭示", critic.soften_leak(t, 2, "mark")["text"])
        self.assertFalse(critic.soften_leak(t, 2, "off")["changed"])

    def test_pass(self):
        r = critic.check("先看差商的定义，它由哪两部分组成？", hint_level=1, has_citation=True)
        self.assertTrue(r["ok"])


class TestStateIntegration(unittest.TestCase):
    def test_asked_stores_question_and_answer(self):
        s = init("s2", concept="导数")
        for e in ("confirm_goal", "diagnosed", "plan_ready"):
            step(s, e)
        step(s, "asked", text="导数定义是什么？", rubric="差商,极限", expected="差商的极限")
        self.assertEqual(s.question, "导数定义是什么？")
        r = step(s, "answer", "correct")
        self.assertEqual(r["state"]["phase"], "ADVANCE")


if __name__ == "__main__":
    unittest.main()
