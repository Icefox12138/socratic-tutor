import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.classifier import classify  # noqa: E402


class TestClassifier(unittest.TestCase):
    def test_evidence(self):
        self.assertEqual(classify("这个判断的依据在哪一卷？")["type"], "evidence")

    def test_hypothesis(self):
        self.assertEqual(classify("如果删去这条注疏，还成立吗？")["type"], "hypothesis")

    def test_meta(self):
        self.assertEqual(classify("你怎么知道自己读对了？")["type"], "meta")

    def test_perspective(self):
        self.assertEqual(classify("王夫之会怎么反驳？")["type"], "perspective")

    def test_inference(self):
        self.assertEqual(classify("若此说成立，后面会怎样？")["type"], "inference")

    def test_clarify_and_multi(self):
        r = classify("你说的‘礼’指哪一层？那它和法呢？")
        self.assertEqual(r["type"], "clarify")
        self.assertEqual(r["questions"], 2)
        self.assertTrue(r["multi"])

    def test_no_question_mark(self):
        self.assertFalse(classify("先看定义")["multi"])


if __name__ == "__main__":
    unittest.main()
