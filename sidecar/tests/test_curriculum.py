"""Curriculum packs (schema v1): the engine consumes lessons, it does not ship them."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _tmp import TemporaryDirectory  # noqa: E402
from app import config, curriculum  # noqa: E402


def _pack(**over):
    p = {
        "schema": 1,
        "lesson_id": "demo-lesson",
        "line": "demo",
        "title": "Demo lesson",
        "unit": 1,
        "lesson": 1,
        "passage": {"source": "demo", "book": "synthetic-book.pdf",
                    "page_start": 1, "page_end": 2},
        "background": "bg",
        "worked_example": "we",
        "vocab": [{"headword": "arma", "lang": "latin", "gloss": "weapons"}],
        "grammar": [{"scheme": "grammar", "section": "§419"}],
        "questions": [{"q": "what?", "rubric": "r",
                       "answer_loc": {"source": "demo", "book": "b", "page": 2}}],
        "review_cards": [{"term": "arma", "definition": "weapons"}],
    }
    p.update(over)
    return p


class TestCurriculum(unittest.TestCase):
    def setUp(self):
        self.old = config.CURRICULUM
        self.addCleanup(self._restore)

    def _restore(self):
        config.CURRICULUM = self.old

    def _dir_with(self, packs):
        d = TemporaryDirectory()
        self.addCleanup(lambda: d.__exit__(None, None, None))
        for name, pack in packs.items():
            with open(os.path.join(d.name, name), "w", encoding="utf-8") as fh:
                json.dump(pack, fh, ensure_ascii=False)
        return d.name

    def test_valid_pack_passes_validation(self):
        self.assertEqual(curriculum.validate(_pack()), [])

    def test_catalog_lists_only_valid_packs(self):
        d = self._dir_with({"a.json": _pack(),
                            "b.json": _pack(lesson_id="broken", questions=[])})
        config.CURRICULUM = d
        cat = curriculum.catalog()
        self.assertEqual([x["lesson_id"] for x in cat["lessons"]], ["demo-lesson"])

    def test_lesson_resolves_and_degrades_without_lexicon(self):
        d = self._dir_with({"a.json": _pack()})
        config.CURRICULUM = d
        out = curriculum.lesson("demo-lesson")
        self.assertIsNotNone(out)
        self.assertTrue(out["available"])
        # no lexicon.db in this environment: entry is None, gloss kept
        self.assertEqual(out["vocab"][0]["headword"], "arma")
        self.assertIn("entry", out["vocab"][0])

    def test_unknown_or_invalid_lesson_is_none(self):
        d = self._dir_with({"a.json": _pack()})
        config.CURRICULUM = d
        self.assertIsNone(curriculum.lesson("nope"))
        bad = self._dir_with({"b.json": _pack(lesson_id="Bad ID")})
        config.CURRICULUM = bad
        self.assertIsNone(curriculum.lesson("Bad ID"))

    def test_missing_dir_is_empty(self):
        config.CURRICULUM = os.path.join(TemporaryDirectory().name, "absent")
        self.assertEqual(curriculum.catalog()["lessons"], [])

    def test_validation_catches_field_problems(self):
        errs = curriculum.validate(_pack(schema=2, unit=0,
                                         passage={"source": "", "book": "",
                                                  "page_start": 5, "page_end": 2},
                                         review_cards=[]))
        joined = " | ".join(errs)
        for needle in ("schema", "unit", "passage.source", "page_end", "review_cards"):
            self.assertIn(needle, joined)

    def test_endpoints_serve_the_catalog_and_one_lesson(self):
        from fastapi import HTTPException
        from app import main
        d = self._dir_with({"a.json": _pack()})
        config.CURRICULUM = d
        cat = main.v1_curriculum()
        self.assertEqual(len(cat["lessons"]), 1)
        one = main.v1_curriculum_lesson("demo-lesson")
        self.assertEqual(one["lesson_id"], "demo-lesson")
        with self.assertRaises(HTTPException) as ctx:
            main.v1_curriculum_lesson("absent")
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
