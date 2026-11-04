import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import citations, policy, search  # noqa: E402


class TestImageOnlyPolicy(unittest.TestCase):
    def setUp(self):
        os.environ.pop("SOCRATIC_IMAGE_ONLY_LANGS", None)
        policy.reload()

    def tearDown(self):
        os.environ.pop("SOCRATIC_IMAGE_ONLY_LANGS", None)
        policy.reload()

    def test_default_languages(self):
        self.assertTrue(policy.image_only("greek"))
        self.assertTrue(policy.image_only("GRC"))
        self.assertFalse(policy.image_only("latin"))
        self.assertFalse(policy.image_only("zh"))
        self.assertFalse(policy.image_only(None))

    def test_env_override_replaces_defaults(self):
        os.environ["SOCRATIC_IMAGE_ONLY_LANGS"] = "latin"
        policy.reload()
        self.assertTrue(policy.image_only("latin"))
        self.assertFalse(policy.image_only("greek"))

    def test_empty_env_restores_defaults(self):
        os.environ["SOCRATIC_IMAGE_ONLY_LANGS"] = "  "
        policy.reload()
        self.assertTrue(policy.image_only("greek"))

    def test_redact_empties_greek_text(self):
        hit = {"chunk_id": 1, "lang": "greek", "text": "λόγος noise",
               "citation": {"locator": "bk p.1", "page_image": "/v1/pages?x=1"}}
        out = policy.redact(hit)
        self.assertEqual(out["text"], "")
        self.assertTrue(out["image_only"])
        self.assertTrue(out["citation"]["image_only"])
        self.assertIn("page-image-only", out["text_omitted"])
        # the input is not mutated: cached payloads keep their raw text
        self.assertEqual(hit["text"], "λόγος noise")

    def test_redact_leaves_latin_alone(self):
        hit = {"chunk_id": 2, "lang": "latin", "text": "arma virumque"}
        self.assertIs(policy.redact(hit), hit)

    def test_row_result_is_redacted_for_greek(self):
        row = {"id": 7, "source": "steadman", "book": "phaedo", "lang": "greek",
               "page": 42, "text": "Σωκράτης"}
        out = search._row_result(row, 0.9)
        self.assertEqual(out["text"], "")
        self.assertTrue(out["image_only"])
        self.assertIn("page=42", out["citation"]["page_image"])

    def test_row_result_keeps_latin_text(self):
        row = {"id": 8, "source": "steadman", "book": "vergil", "lang": "latin",
               "page": 3, "text": "arma virumque cano"}
        out = search._row_result(row, 0.5)
        self.assertEqual(out["text"], "arma virumque cano")
        self.assertNotIn("image_only", out)


class TestCitationSnippet(unittest.TestCase):
    def test_greek_citation_stores_no_snippet(self):
        path = os.path.join(tempfile.mkdtemp(), "c.db")
        results = [
            {"chunk_id": 1, "source": "steadman", "book": "phaedo", "page": 1,
             "lang": "greek", "text": "", "image_only": True,
             "citation": {"locator": "phaedo p.1", "page_image": "/v1/pages?a=1"}},
            {"chunk_id": 2, "source": "library", "book": "bk", "page": 2,
             "lang": "latin", "text": "arma virumque",
             "citation": {"locator": "bk p.2", "page_image": "/v1/pages?a=2"}},
        ]
        citations.add_many("s1", results, path=path)
        rows = {r["chunk_id"]: r for r in citations.list_for("s1", path=path)}
        self.assertEqual(rows[1]["snippet"], "")
        self.assertEqual(rows[2]["snippet"], "arma virumque")
        self.assertEqual(rows[1]["page_image"], "/v1/pages?a=1")


if __name__ == "__main__":
    unittest.main()
