import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import review, state_machine  # noqa: E402


class TestJudge(unittest.TestCase):
    def test_exact_math(self):
        self.assertEqual(review.judge("3*x**2", "3*x**2")[0], "correct")

    def test_equivalent_forms(self):
        self.assertEqual(review.judge("x + x", "2*x")[0], "correct")
        self.assertEqual(review.judge("0.5", "1/2")[0], "correct")

    def test_wrong(self):
        self.assertEqual(review.judge("4*x**2", "3*x**2")[0], "incorrect")

    def test_solution_set_order_insensitive(self):
        self.assertEqual(review.judge("[-2, 2]", "[2, -2]")[0], "correct")

    def test_no_expected_is_undetermined(self):
        self.assertEqual(review.judge("3*x**2", "")[0], "undetermined")

    def test_prose_is_not_forced_to_correct(self):
        self.assertEqual(review.judge("我认为是切线斜率", "3*x**2")[0], "undetermined")


class TestClassify(unittest.TestCase):
    def check(self, claim, expected, want):
        self.assertEqual(review.classify(claim, expected), want, "%s vs %s" % (claim, expected))

    def test_sign(self):
        self.check("-3*x**2", "3*x**2", "sign")

    def test_arithmetic(self):
        self.check("4*x**2", "3*x**2", "arithmetic")
        self.check("512", "1024", "arithmetic")

    def test_formula(self):
        self.check("x**3", "3*x**2", "formula")
        self.check("sin(x)", "cos(x)", "formula")

    def test_condition(self):
        self.check("[3]", "[3, -3]", "condition")

    def test_unit(self):
        self.check("1024000", "1024", "unit")

    def test_incomplete(self):
        self.check("x**2 + 2*x", "x**2 + 2*x + 1", "incomplete")

    def test_misread(self):
        self.check("3*y**2", "3*x**2", "misread")


class TestClaims(unittest.TestCase):
    def test_question_is_not_a_claim(self):
        claims = review.extract_claims("这道题的导数是什么？")
        self.assertTrue(claims)
        self.assertFalse(claims[0]["claim"])
        self.assertEqual(claims[0]["reason"], "question")

    def test_paraphrase_is_not_a_claim(self):
        claims = review.extract_claims("也就是说，导数是切线斜率。")
        self.assertFalse(claims[0]["claim"])
        self.assertEqual(claims[0]["reason"], "paraphrase")

    def test_answer_is_a_claim(self):
        claims = review.extract_claims("我认为答案是 3x^2。")
        self.assertTrue(claims[0]["claim"])


class TestAttribute(unittest.TestCase):
    def test_missing_expected_blames_the_question(self):
        self.assertEqual(review.attribute({"question": "求导"}, "x", "incorrect", ""), "question")

    def test_greek_material(self):
        st = {"question": "What does quīdam do in alveō?", "lang": "greek", "concept": "c"}
        self.assertEqual(review.attribute(st, "x", "incorrect", "y"), "material")

    def test_defaults_to_student(self):
        st = {"question": "求 x^3 的导数，并说明每一步", "lang": "zh", "concept": "c1"}
        self.assertEqual(review.attribute(st, "x", "incorrect", "y"), "student")


class TestReview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.db = os.path.join(self.tmp, "state.db")

    def test_report_counts_and_practice(self):
        st = {"session_id": "s1", "question": "求 x^3 的导数", "expected": "3*x**2",
              "concept": "derivative", "lang": "zh",
              "history": [{"event": "answer", "result": "wrong", "text": "我算的是 4x^2。"},
                          {"event": "answer", "result": "correct", "text": "那应该是 3x^2。"}]}
        rep = review.review("s1", st, path=self.db)
        self.assertEqual(rep["summary"]["n_claims"], 2)
        self.assertEqual(rep["summary"]["correct"], 1)
        self.assertEqual(rep["summary"]["incorrect"], 1)
        self.assertEqual(rep["summary"]["errors"], {"arithmetic": 1})
        self.assertEqual(len(rep["practice"]), 1)
        self.assertEqual(rep["practice"][0]["error"], "arithmetic")
        self.assertEqual(rep["digest"], rep["digest"].lower())

    def test_questions_are_excluded_from_accuracy(self):
        st = {"question": "求导", "expected": "3*x**2", "concept": "d", "lang": "zh",
              "history": [{"text": "这是什么意思？"}, {"text": "3x^2"}]}
        rep = review.review("s2", st, path=self.db)
        self.assertEqual(rep["summary"]["n_claims"], 1)
        self.assertEqual(rep["summary"]["accuracy"], 1.0)
        self.assertEqual(rep["claims"][0]["verdict"], "not_a_claim")

    def test_no_expected_means_undetermined(self):
        st = {"question": "说说你的思路", "expected": "", "concept": "d", "lang": "zh",
              "history": [{"text": "先求导再代入"}]}
        rep = review.review("s3", st, path=self.db)
        self.assertEqual(rep["summary"]["undetermined"], 1)
        self.assertEqual(rep["summary"]["accuracy"], 0.0)

    def test_answer_text_is_persisted_by_the_state_machine(self):
        s = state_machine.State(session_id="s4", phase="WAIT")
        s.expected = "3*x**2"
        state_machine.step(s, "answer", "wrong", text="我算的是 4x^2")
        self.assertEqual(s.history[-1]["text"], "我算的是 4x^2")


if __name__ == "__main__":
    unittest.main()
