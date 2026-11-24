"""Lexicon lookup (schema v2.1): exact headword / section, never vector."""
import json
import os
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _tmp import TemporaryDirectory  # noqa: E402
from app import citation_policy, config, lexicon, schema  # noqa: E402


def _fixture(path):
    schema.ensure_v2(path)
    con = sqlite3.connect(path)
    con.execute("INSERT INTO sources(source_id, adapter, license) "
                "VALUES('lsj','lexicon','CC BY-SA')")
    con.execute("INSERT INTO sources(source_id, adapter, license) "
                "VALUES('smyth','lexicon','public-domain')")
    con.execute(
        "INSERT INTO documents(document_id, source_id, title, kind, canonical_url) "
        "VALUES('d-lsj','lsj','A Greek-English Lexicon','dictionary',"
        "'https://www.perseus.tufts.edu/hopper/text?doc=Perseus:text:1999.04.0057')")
    con.execute(
        "INSERT INTO documents(document_id, source_id, title, kind) "
        "VALUES('d-smyth','smyth','A Greek Grammar','grammar')")
    # entry body: a definition chunk whose locator is the dict scheme
    con.execute(
        "INSERT INTO chunks(id, document_id, ordinal, section, text, stream, "
        "locator_json) VALUES(1,'d-lsj',1,'λύω','λύω, ἔλυσα: to loose, untie.',"
        "'definition',?)",
        (json.dumps({"scheme": "dict", "headword": "λύω", "pos": "v",
                     "sense": "1", "page": 345}, ensure_ascii=False),))
    con.execute(
        "INSERT INTO chunks(id, document_id, ordinal, section, text, stream, "
        "locator_json) VALUES(2,'d-smyth',1,'§212','Absolute ablative.',"
        "'paradigm',?)",
        (json.dumps({"scheme": "grammar", "section": "§212",
                     "title": "Absolute ablative", "smythp": "2297"},
                    ensure_ascii=False),))
    con.execute("INSERT INTO lexicon_headwords(lang, headword, lemma, pos, homonym,"
                " entry_id, source_id) VALUES('greek','λύω','λύω','v',0,1,'lsj')")
    con.execute("INSERT INTO lexicon_headwords(lang, headword, lemma, pos, homonym,"
                " entry_id, source_id) VALUES('greek','§212','Absolute ablative',"
                "'',0,2,'smyth')")
    con.commit()
    con.close()


class TestLexiconLookup(unittest.TestCase):
    def setUp(self):
        self.old = config.LEXICON_DB
        self.addCleanup(self._restore)

    def _restore(self):
        config.LEXICON_DB = self.old
        lexicon.reset()

    def test_schema_creates_the_table(self):
        with TemporaryDirectory() as d:
            path = os.path.join(d, "lex.db")
            schema.ensure_v2(path)
            con = sqlite3.connect(path)
            tables = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            con.close()
            self.assertIn("lexicon_headwords", tables)

    def test_dictionary_entry_with_body_and_citation(self):
        with TemporaryDirectory() as d:
            path = os.path.join(d, "lex.db")
            _fixture(path)
            out = lexicon.lookup("λύω", lang="greek", path=path)
            self.assertTrue(out["available"])
            self.assertEqual(out["reason"], None)
            entry = out["entries"][0]
            self.assertEqual(entry["headword"], "λύω")
            self.assertIn("to loose", entry["definition"])
            self.assertEqual(entry["citation"]["scheme"], "dict")
            self.assertEqual(entry["citation"]["tier"], "A")
            self.assertIn("λύω", entry["citation"]["label"])

    def test_grammar_section_accepts_several_spellings(self):
        with TemporaryDirectory() as d:
            path = os.path.join(d, "lex.db")
            _fixture(path)
            for form in ("§212", "212"):
                out = lexicon.lookup(form, area="grammar", path=path)
                self.assertEqual(len(out["entries"]), 1, form)
                citation = out["entries"][0]["citation"]
                self.assertEqual(citation["scheme"], "grammar")
                self.assertIn("smythp=2297", citation["url"] or "")
            # smythp is a separate numbering: it must not be guessed into §212.
            out = lexicon.lookup("smythp=2297", area="grammar", path=path)
        self.assertEqual(out["reason"], "not_found")

    def test_missing_database_degrades(self):
        with TemporaryDirectory() as d:
            out = lexicon.lookup("λύω", path=os.path.join(d, "absent.db"))
        self.assertFalse(out["available"])
        self.assertEqual(out["reason"], "no_lexicon")
        self.assertEqual(out["entries"], [])

    def test_unknown_headword_reports_not_found(self):
        with TemporaryDirectory() as d:
            path = os.path.join(d, "lex.db")
            _fixture(path)
            out = lexicon.lookup("ἄγνωστος", lang="greek", path=path)
        self.assertEqual(out["reason"], "not_found")

    def test_student_streams_include_definitions_for_a_dictionary(self):
        with TemporaryDirectory() as d:
            path = os.path.join(d, "lex.db")
            _fixture(path)
            out = lexicon.lookup("λύω", lang="greek", path=path)
        self.assertIn("definition", out["streams"])

    def test_all_senses_of_an_entry_are_joined(self):
        """v2.1 lexicon databases set chunks.entry_id on every sense chunk."""
        with TemporaryDirectory() as d:
            path = os.path.join(d, "lex.db")
            _fixture(path)
            con = sqlite3.connect(path)
            con.execute("ALTER TABLE chunks ADD COLUMN entry_id INTEGER")
            con.execute("UPDATE chunks SET entry_id = 1 WHERE id = 1")
            con.execute(
                "INSERT INTO chunks(id, document_id, ordinal, section, text, stream,"
                " locator_json, entry_id) VALUES(3,'d-lsj',3,'λ',"
                "'λύω: a second sense, to loosen.',"
                "'definition',?,1)",
                (json.dumps({"scheme": "dict", "headword": "λύω", "pos": "v",
                             "sense": "2"}, ensure_ascii=False),))
            con.commit()
            con.close()
            out = lexicon.lookup("λύω", lang="greek", path=path)
        self.assertEqual(len(out["entries"]), 1)
        body = out["entries"][0]["definition"]
        self.assertIn("to loose", body)
        self.assertIn("second sense", body)

    def test_a_long_entry_pages_by_character_window(self):
        """λόγος is ~24 KB: the caller gets a slice plus next_offset."""
        with TemporaryDirectory() as d:
            path = os.path.join(d, "lex.db")
            _fixture(path)
            con = sqlite3.connect(path)
            con.execute("ALTER TABLE chunks ADD COLUMN entry_id INTEGER")
            con.execute("UPDATE chunks SET entry_id = 1 WHERE id = 1")
            con.execute(
                "INSERT INTO chunks(id, document_id, ordinal, section, text, stream,"
                " locator_json, entry_id) VALUES(3,'d-lsj',3,'λ',?,"
                "'definition',?,1)",
                ("B" * 40, json.dumps({"scheme": "dict", "headword": "λύω",
                                       "pos": "v", "sense": "2"})))
            con.commit()
            con.close()

            full = lexicon.lookup("λύω", lang="greek", path=path)["entries"][0]
            total = full["definition_total"]
            self.assertGreater(total, 50)
            self.assertFalse(full["definition_truncated"])
            self.assertIsNone(full["next_offset"])

            page = lexicon.lookup("λύω", lang="greek", path=path,
                                 entry_offset=0, entry_limit=10)["entries"][0]
            self.assertEqual(len(page["definition"]), 10)
            self.assertTrue(page["definition_truncated"])
            self.assertEqual(page["next_offset"], 10)
            self.assertEqual(page["definition_total"], total)
            # the second window continues exactly where the first stopped
            tail = lexicon.lookup("λύω", lang="greek", path=path,
                                 entry_offset=10, entry_limit=10)["entries"][0]
            self.assertEqual(tail["definition_offset"], 10)
            self.assertEqual(len(tail["definition"]), 10)
            # a window that reaches the end is not truncated
            end = lexicon.lookup("λύω", lang="greek", path=path,
                                entry_offset=total - 5)["entries"][0]
            self.assertFalse(end["definition_truncated"])
            self.assertIsNone(end["next_offset"])


class TestLexiconEndpoint(unittest.TestCase):
    def setUp(self):
        self.old = config.LEXICON_DB
        self.addCleanup(self._restore)

    def _restore(self):
        config.LEXICON_DB = self.old
        lexicon.reset()

    def test_endpoint_returns_entries(self):
        from fastapi import HTTPException  # noqa: F401
        from app import main
        with TemporaryDirectory() as d:
            config.LEXICON_DB = os.path.join(d, "lex.db")
            _fixture(config.LEXICON_DB)
            out = main.v1_lexicon(q="λύω", lang="greek", area="dict",
                                  view="student", limit=10)
        self.assertEqual(len(out["entries"]), 1)

    def test_endpoint_pages_a_long_entry(self):
        from fastapi import HTTPException  # noqa: F401
        from app import main
        with TemporaryDirectory() as d:
            config.LEXICON_DB = os.path.join(d, "lex.db")
            _fixture(config.LEXICON_DB)
            out = main.v1_lexicon(q="λύω", lang="greek", area="dict",
                                  view="student", limit=10,
                                  entry_offset=0, entry_limit=5)
        entry = out["entries"][0]
        self.assertEqual(len(entry["definition"]), 5)
        self.assertTrue(entry["definition_truncated"])
        self.assertEqual(entry["next_offset"], 5)

    def test_endpoint_rejects_a_bad_area(self):
        from fastapi import HTTPException
        from app import main
        with self.assertRaises(HTTPException) as ctx:
            main.v1_lexicon(q="λύω", lang=None, area="etymology",
                            view="student", limit=10)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_policy_names_a_lexicon_catalogue(self):
        policy = citation_policy.effective()
        self.assertEqual(policy["sources"]["dict-lsj"]["locator_scheme"], "dict")
        self.assertEqual(policy["sources"]["grammar-smyth"]["catalogue"], "lexicon")
        kinds = {c["kind"] for c in policy["channels"]}
        self.assertIn("lexicon-sqlite", kinds)


if __name__ == "__main__":
    unittest.main()
