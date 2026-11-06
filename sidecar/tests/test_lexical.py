import os
import shutil
import sqlite3
import unittest
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _tmp import mkdtemp  # noqa: E402

from fastapi.testclient import TestClient

from app import config, ingest, lexical, main, schema, translate
from app.adapters.base import Document, Section, SourceSpec


def _doc(document_id, source_id, title, lang, section, text, locator):
    return Document(
        document_id=document_id, source_id=source_id, title=title, lang=lang,
        license="PD-old", source_version="1",
        sections=[Section(title=section, text=text, locator=locator)])


def _spec(source_id):
    return SourceSpec(source_id=source_id, adapter="mediawiki",
                      base_url="https://example.invalid/w/api.php",
                      license="PD-old")


class _Base(unittest.TestCase):
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
            ("wikisource:zh:史記/卷001", 99, "補編", "答案：黃帝是少典之子。",
             "zh-classical", "text", "answer_key",
             '{"scheme":"mediawiki","site":"x","title":"y","revision":"1"}',
             "答案", "t"))
        con.commit()
        con.close()

        self.old = (config.DB, config.SCHEMA, config.BGE, config.TRANSLATE)
        config.DB, config.SCHEMA, config.BGE = self.db, "auto", False
        config.TRANSLATE = "off"
        translate.clear_cache()
        self.addCleanup(self._restore)

    def _restore(self):
        config.DB, config.SCHEMA, config.BGE, config.TRANSLATE = self.old
        translate.clear_cache()


class TestGrep(_Base):
    def test_chinese_substring_and_match_offsets(self):
        out = lexical.grep("少典之子")
        self.assertEqual(out["mode"], "grep")
        self.assertEqual(out["schema"], "v2")
        hit = out["results"][0]
        self.assertEqual(hit["document_id"], "wikisource:zh:史記/卷001")
        self.assertEqual(hit["citation"]["scheme"], "mediawiki")
        self.assertEqual(out["results"][0]["match"]["count"], 1)
        text = hit["text"]
        self.assertEqual(text[hit["match"]["start"]:hit["match"]["end"]], "少典之子")

    def test_latin_case_insensitive(self):
        out = lexical.grep("iunonis")
        self.assertEqual(out["results"][0]["document_id"],
                         "urn:cts:latinLit:phi0690.phi003.perseus-lat1")

    def test_answer_key_is_never_returned(self):
        self.assertEqual(lexical.grep("答案")["results"], [])

    def test_filters(self):
        self.assertEqual(lexical.grep("μῆνιν", section="1.1")["results"][0]["section"], "1.1")
        self.assertEqual(lexical.grep("μῆνιν", document_id="urn:cts:latinLit:phi0690.phi003.perseus-lat1")["results"], [])

    def test_missing_substring(self):
        self.assertEqual(lexical.grep("不存在的字符串")["results"], [])


class TestLemma(_Base):
    def test_greek_inflection_matches(self):
        # μῆνις is not a substring of μῆνιν; only the lemma/stem channel hits.
        self.assertEqual(lexical.grep("μῆνις")["results"], [])
        out = lexical.lemma_search("μῆνις")
        self.assertEqual(out["mode"], "lemma")
        self.assertEqual(out["results"][0]["document_id"],
                         "urn:cts:greekLit:tlg0012.tlg001.perseus-grc1")
        self.assertGreaterEqual(out["results"][0]["match"]["coverage"], 0.5)

    def test_latin_inflection_matches(self):
        # irae is not a substring of iram.
        self.assertEqual(lexical.grep("irae")["results"], [])
        out = lexical.lemma_search("irae")
        self.assertEqual(out["results"][0]["section"], "1.4")

    def test_chinese_lemma_is_bigram_matching(self):
        out = lexical.lemma_search("黃帝")
        self.assertEqual(out["results"][0]["document_id"], "wikisource:zh:史記/卷001")

    def test_v1_lemma_is_rejected(self):
        old = config.DB
        v1 = os.path.join(self.tmp, "v1.db")
        con = sqlite3.connect(v1)
        con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, source TEXT, book TEXT,"
                    " lang TEXT, page INTEGER, text TEXT, visibility TEXT)")
        con.commit()
        con.close()
        config.DB = v1
        self.addCleanup(lambda: setattr(config, "DB", old))
        with self.assertRaises(ValueError):
            lexical.lemma_search("x")


class TestEndpoints(_Base):
    def test_grep_endpoint(self):
        r = TestClient(main.app).get("/v1/grep", params={"q": "少典之子"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["mode"], "grep")
        self.assertEqual(r.json()["results"][0]["match"]["count"], 1)

    def test_lemma_endpoint(self):
        r = TestClient(main.app).get("/v1/lemma", params={"q": "μῆνις"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["results"][0]["section"], "1.1")

    def test_bad_view(self):
        r = TestClient(main.app).get("/v1/grep", params={"q": "x", "view": "nope"})
        self.assertEqual(r.status_code, 400)


class TestGrepV1(unittest.TestCase):
    def setUp(self):
        self.tmp = mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.db = os.path.join(self.tmp, "search.db")
        con = sqlite3.connect(self.db)
        con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, source TEXT, book TEXT,"
                    " lang TEXT, page INTEGER, text TEXT, visibility TEXT)")
        con.execute("INSERT INTO chunks VALUES (1,'library','b.pdf','latin',10,"
                    "'Arma virumque cano, Troiae qui primus ab oris','tutor')")
        con.commit()
        con.close()
        self.old = (config.DB, config.SCHEMA)
        config.DB, config.SCHEMA = self.db, "auto"
        self.addCleanup(self._restore)

    def _restore(self):
        config.DB, config.SCHEMA = self.old

    def test_grep_returns_page_citation(self):
        out = lexical.grep("virumque")
        hit = out["results"][0]
        self.assertEqual(out["schema"], "v1")
        self.assertEqual(hit["page"], 10)
        self.assertEqual(hit["document_id"], "library:b.pdf")
        self.assertIn("virumque", hit["text"])


if __name__ == "__main__":
    unittest.main()
