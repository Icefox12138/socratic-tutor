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


class TestLexiconEndpoint(unittest.TestCase):
    def setUp(self):
        self.old = config.LEXICON_DB
        self.addCleanup(self._restore)

    def _restore(self):
        config.LEXICON_DB = self.old

    def test_endpoint_returns_entries(self):
        from fastapi import HTTPException  # noqa: F401
        from app import main
        with TemporaryDirectory() as d:
            config.LEXICON_DB = os.path.join(d, "lex.db")
            _fixture(config.LEXICON_DB)
            out = main.v1_lexicon(q="λύω", lang="greek", area="dict",
                                  view="student", limit=10)
        self.assertEqual(len(out["entries"]), 1)

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
