import os
import shutil
import sqlite3
import unittest
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _tmp import mkdtemp  # noqa: E402

from app import config, ingest, schema, search
from app.adapters.base import Document, Section, SourceSpec


def _doc(document_id, source_id, title, lang, section, text, locator):
    return Document(
        document_id=document_id, source_id=source_id, title=title, lang=lang,
        license="PD-old", source_version="1",
        sections=[Section(title=section, text=text, locator=locator)])


def _spec(source_id):
    return SourceSpec(source_id=source_id, adapter="mediawiki",
                      base_url="https://example.invalid/w/api.php", license="PD-old")


class TestV2LexicalFusion(unittest.TestCase):
    def setUp(self):
        self.tmp = mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.db = os.path.join(self.tmp, "public.db")
        schema.ensure_v2(self.db)
        ingest.ingest(self.db, _doc(
            "wikisource:zh:史記/卷001", "wikisource:zh", "史記/卷001",
            "zh-classical", "黃帝", "黃帝者，少典之子，姓公孫，名曰軒轅。",
            {"scheme": "mediawiki", "site": "zh.wikisource.org",
             "title": "史記/卷001", "revision": "1", "section": "黃帝"}),
            _spec("wikisource:zh"))
        ingest.ingest(self.db, _doc(
            "urn:cts:greekLit:tlg0012.tlg001.perseus-grc1", "perseus",
            "Iliad", "greek", "1.1",
            "μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος",
            {"scheme": "cts",
             "urn": "urn:cts:greekLit:tlg0012.tlg001.perseus-grc1:1.1",
             "work": "urn:cts:greekLit:tlg0012.tlg001.perseus-grc1",
             "book": "1", "line_start": 1, "line_end": 1}),
            _spec("perseus"))
        ingest.ingest(self.db, _doc(
            "urn:cts:latinLit:phi0690.phi003.perseus-lat1", "perseus",
            "Aeneid", "latin", "1.4",
            "vi superum saevae memorem Iunonis ob iram;",
            {"scheme": "cts",
             "urn": "urn:cts:latinLit:phi0690.phi003.perseus-lat1:1.4",
             "work": "urn:cts:latinLit:phi0690.phi003.perseus-lat1",
             "book": "1", "line_start": 4, "line_end": 4}),
            _spec("perseus"))
        con = sqlite3.connect(self.db)
        con.execute(
            "INSERT INTO chunks(document_id, ordinal, section, text, lang,"
            " stream, visibility, locator_json, citation_label, quality)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            ("wikisource:zh:史記/卷001", 99, "補編", "答案：少典之子。",
             "zh-classical", "text", "answer_key",
             '{"scheme":"mediawiki","site":"x","title":"y","revision":"1"}',
             "答案", "t"))
        con.commit()
        con.close()

        self.old = (config.DB, config.SCHEMA, config.BGE, config.TRANSLATE,
                    config.LEXICAL)
        config.DB, config.SCHEMA, config.BGE = self.db, "auto", False
        config.TRANSLATE, config.LEXICAL = "off", "auto"
        self.addCleanup(self._restore)

    def _restore(self):
        (config.DB, config.SCHEMA, config.BGE, config.TRANSLATE,
         config.LEXICAL) = self.old

    def test_exact_quote_uses_grep(self):
        out = search.search("少典之子")
        self.assertGreater(out["lexical"]["grep"], 0)
        self.assertEqual(out["results"][0]["document_id"],
                         "wikisource:zh:史記/卷001")
        self.assertEqual(out["results"][0]["citation"]["scheme"], "mediawiki")

    def test_greek_inflection_uses_lemma(self):
        out = search.search("μῆνις")
        self.assertGreater(out["lexical"]["lemma"], 0)
        self.assertEqual(out["results"][0]["document_id"],
                         "urn:cts:greekLit:tlg0012.tlg001.perseus-grc1")

    def test_latin_inflection_uses_lemma(self):
        out = search.search("irae")
        self.assertGreater(out["lexical"]["lemma"], 0)
        self.assertEqual(out["results"][0]["section"], "1.4")

    def test_lexical_off_leaves_only_fts(self):
        config.LEXICAL = "off"
        out = search.search("μῆνις")
        self.assertEqual(out["lexical"], {"grep": 0, "lemma": 0})
        self.assertEqual(out["results"], [])

    def test_answer_key_never_surfaces(self):
        out = search.search("少典之子")
        self.assertFalse(any(r["chunk_id"] == 99 for r in out["results"]))


if __name__ == "__main__":
    unittest.main()
