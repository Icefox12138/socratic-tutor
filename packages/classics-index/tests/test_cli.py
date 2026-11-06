import json
import os
import secrets
import shutil
import tempfile
import unittest

from classics_index import cli


def mkdtemp(suffix=None, prefix=None, dir=None):
    """tempfile.mkdtemp() yields a directory the DSH Windows sandbox cannot write
    into (owner-only DACL), so build an ordinary one instead."""
    base = dir or tempfile.gettempdir()
    path = os.path.join(base, (prefix or "tmp") + secrets.token_hex(6) + (suffix or ""))
    os.makedirs(path)
    return path

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EX = os.path.join(HERE, "examples")


class TestCliOnExamples(unittest.TestCase):
    def test_volumes_and_pian_match_expected(self):
        tmp = mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        toc = os.path.join(tmp, "toc.json")
        idx = os.path.join(tmp, "index.json")
        cli.main(["volumes", "--headers", os.path.join(EX, "demo-headers.jsonl"),
                  "--out", toc])
        cli.main(["pian", "--toc", toc,
                  "--band", os.path.join(EX, "demo-titles.jsonl"), "--out", idx])
        got = json.load(open(idx, encoding="utf-8"))["chapters"]
        want = json.load(open(os.path.join(EX, "expected-toc.json"), encoding="utf-8"))["chapters"]
        self.assertEqual(len(got), len(want))
        for g, w in zip(got, want):
            self.assertEqual(g["title"], w["title"])
            self.assertEqual((g["page_start"], g["page_end"]), (w["page_start"], w["page_end"]))
            self.assertEqual(g["level"], w["level"])

    def test_find_and_at(self):
        tmp = mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        toc = os.path.join(tmp, "toc.json")
        cli.main(["volumes", "--headers", os.path.join(EX, "demo-headers.jsonl"), "--out", toc])
        rows = json.load(open(toc, encoding="utf-8"))["chapters"]
        self.assertEqual(rows[1]["page_start"], 3)
        self.assertIn("卷1", rows[1]["title"])


if __name__ == "__main__":
    unittest.main()
