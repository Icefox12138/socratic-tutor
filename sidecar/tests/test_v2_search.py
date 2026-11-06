import os
import shutil
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

from app import config, ingest, main, schema, search, textutil
from app.adapters.base import Document, Section, SourceSpec


def _mediawiki_doc(doc_id, title, lang, sections, revision="123", license="PD-old",
                   source_id="wikisource:zh"):
    return Document(
        document_id=doc_id, source_id=source_id,
        title=title, lang=lang, license=license, source_version=revision,
        canonical_url="https://example.invalid/wiki/%s?oldid=%s" % (title, revision),
        sections=[Section(title=h, text=t, locator={
            "scheme": "mediawiki", "site": "example.invalid", "title": title,
            "revision": revision, "section": h}) for h, t in sections])


def _insert_chunk(db, document_id, text, stream="text", visibility="tutor",
                  lang="zh-classical", section="補編", label="補編"):
    con = sqlite3.connect(db)
    try:
        cur = con.execute(
            "INSERT INTO chunks(document_id, ordinal, section, text, lang, stream,"
            " visibility, locator_json, citation_label, quality)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (document_id, 999, section, text, lang, stream, visibility,
             '{"scheme":"mediawiki","site":"example.invalid","title":"x",'
             '"revision":"123","section":"%s"}' % section, label, "test"))
        con.execute("INSERT INTO chunks_fts(rowid, text) VALUES(?, ?)",
                    (cur.lastrowid, " ".join(textutil.tokens_v2(text))))
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


class _V2Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.db = os.path.join(self.tmp, "public.db")
        schema.ensure_v2(self.db)

        zh = _mediawiki_doc("wikisource:zh:道德經", "道德經", "zh-classical", [
            ("第一章", "道可道，非常道。名可名，非常名。"),
            ("第二章", "天下皆知美之為美，斯惡已。"),
        ])
        la = _mediawiki_doc("wikisource:la:Aeneis", "Aeneis", "latin", [
            ("Liber I", "Arma virumque cano, Troiae qui primus ab oris"),
        ], source_id="wikisource:la")
        grc = _mediawiki_doc("wikisource:el:Ilias", "Ilias", "greek", [
            ("A", "ἄνδρα μοι ἔννεπε, μοῦσα, πολύτροπον"),
        ], source_id="wikisource:el")
        for doc in (zh, la, grc):
            ingest.ingest(self.db, doc, SourceSpec(
                source_id=doc.source_id, adapter="mediawiki",
                base_url="https://example.invalid/w/api.php",
                license=doc.license, redistribution="share-alike", rate_limit=1.0))
        self.commentary_id = _insert_chunk(
            self.db, "wikisource:zh:道德經", "注釋：道不可言說。", stream="commentary")
        self.answer_id = _insert_chunk(
            self.db, "wikisource:zh:道德經", "答案：非常道即非恆常之道。",
            visibility="answer_key")

        self.old = (config.DB, config.BGE, config.SCHEMA, config.TRANSLATE,
                    config.LEXICAL)
        config.DB, config.BGE, config.SCHEMA = self.db, False, "auto"
        config.TRANSLATE = "off"
        config.LEXICAL = "off"
        self.addCleanup(self._restore)

    def _restore(self):
        (config.DB, config.BGE, config.SCHEMA, config.TRANSLATE,
         config.LEXICAL) = self.old


class TestV2Search(_V2Base):
    def test_chinese_hit_carries_a_mediawiki_citation(self):
        out = search.search("道可道")
        self.assertEqual(out["schema"], "v2")
        self.assertEqual(out["mode"], "fts-public")
        hit = out["results"][0]
        self.assertEqual(hit["document_id"], "wikisource:zh:道德經")
        self.assertEqual(hit["page"], None)
        self.assertEqual(hit["section"], "第一章")
        cit = hit["citation"]
        self.assertEqual(cit["scheme"], "mediawiki")
        self.assertEqual(cit["revision"], "123")
        self.assertEqual(cit["license"], "PD-old")
        self.assertIsNone(cit["page_image"])
        self.assertIn("oldid=123", cit["url"])
        self.assertIn("道德經", cit["locator"])

    def test_latin_and_greek_are_searchable(self):
        self.assertEqual(search.search("virumque")["results"][0]["lang"], "latin")
        self.assertEqual(search.search("ἄνδρα")["results"][0]["lang"], "greek")

    def test_filters(self):
        self.assertTrue(search.search("道可道", source="wikisource:zh")["results"])
        self.assertFalse(search.search("道可道", source="wikisource:la")["results"])
        self.assertFalse(search.search("道可道", lang="latin")["results"])
        self.assertEqual(search.search("道可道", document_id="wikisource:zh:道德經")
                         ["results"][0]["document_id"], "wikisource:zh:道德經")
        self.assertEqual(search.search("天下皆知", section="第二章")["results"][0]["section"],
                         "第二章")

    def test_commentary_is_tutor_only(self):
        self.assertFalse(search.search("注釋", view="student")["results"])
        self.assertTrue(search.search("注釋", view="tutor")["results"])

    def test_answer_key_never_leaves_the_database(self):
        for view in ("student", "tutor"):
            self.assertFalse(search.search("答案", view=view)["results"])

    def test_verify_reads_the_section(self):
        ok = search.verify(document_id="wikisource:zh:道德經",
                           quote="名可名，非常名")
        self.assertTrue(ok["verified"])
        self.assertEqual(ok["scheme"], "mediawiki")
        bad = search.verify(document_id="wikisource:zh:道德經",
                            quote="并不存在的句子")
        self.assertFalse(bad["verified"])
        wrong_rev = search.verify(document_id="wikisource:zh:道德經",
                                  quote="道可道", revision="999")
        self.assertFalse(wrong_rev["verified"])
        self.assertIn("revision mismatch", wrong_rev["reason"])

    def test_health_reports_v2_census(self):
        body = search.health()
        self.assertEqual(body["schema"], "v2")
        self.assertEqual(body["documents"], 3)
        self.assertEqual(body["sources"], 3)
        self.assertGreater(body["chunks"], 3)


class TestV2Endpoints(_V2Base):
    def setUp(self):
        super().setUp()
        self.client = TestClient(main.app)

    def test_health(self):
        body = self.client.get("/health").json()
        self.assertEqual(body["schema"], "v2")
        self.assertEqual(body["documents"], 3)

    def test_sources_and_documents(self):
        sources = self.client.get("/v1/sources").json()
        self.assertEqual(sources["schema"], "v2")
        self.assertEqual({s["source_id"] for s in sources["sources"]},
                         {"wikisource:zh", "wikisource:la", "wikisource:el"})
        docs = self.client.get("/v1/documents", params={"lang": "latin"}).json()
        self.assertEqual([d["document_id"] for d in docs["documents"]],
                         ["wikisource:la:Aeneis"])

    def test_document_detail_accepts_slashes(self):
        r = self.client.get("/v1/documents/wikisource:zh:道德經")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["scheme"], "mediawiki")
        self.assertIn("第一章", [s["section"] for s in body["sections"]])
        self.assertGreaterEqual(body["chunks"], 2)

    def test_search_endpoint(self):
        r = self.client.get("/v1/search", params={"q": "道可道"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["schema"], "v2")
        self.assertIn("oldid=123", body["results"][0]["citation"]["url"])

    def test_chunk_endpoint(self):
        chunk_id = search.search("道可道")["results"][0]["chunk_id"]
        r = self.client.get("/v1/chunks/%d" % chunk_id)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["citation"]["scheme"], "mediawiki")
        self.assertEqual(self.client.get("/v1/chunks/999999").status_code, 404)

    def test_verify_endpoint(self):
        r = self.client.get("/v1/verify", params={
            "document_id": "wikisource:zh:道德經", "quote": "非常名"})
        self.assertTrue(r.json()["verified"])
        bad = self.client.get("/v1/verify", params={"quote": "x"})
        self.assertEqual(bad.status_code, 400)

    def test_commentary_chunk_hidden_from_student(self):
        r = self.client.get("/v1/chunks/%d" % self.commentary_id, params={"view": "student"})
        self.assertEqual(r.status_code, 404)
        r = self.client.get("/v1/chunks/%d" % self.commentary_id, params={"view": "tutor"})
        self.assertEqual(r.status_code, 200)


class TestV1StillWorks(unittest.TestCase):
    def test_v1_schema_is_reported_and_documents_are_absent(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        db = os.path.join(tmp, "search.db")
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, source TEXT, book TEXT,"
                    " lang TEXT, page INTEGER, text TEXT, visibility TEXT)")
        con.execute("CREATE VIRTUAL TABLE chunks_fts USING fts5(text, tokenize='unicode61')")
        con.execute("INSERT INTO chunks VALUES (1,'library','b.pdf','latin',10,"
                    "'Arma virumque cano','tutor')")
        con.execute("INSERT INTO chunks_fts(rowid, text) VALUES (1, 'arma virumque cano')")
        con.commit()
        con.close()
        old = (config.DB, config.BGE, config.SCHEMA, config.TRANSLATE,
               config.LEXICAL)
        config.DB, config.BGE, config.SCHEMA = db, False, "auto"
        config.TRANSLATE = "off"
        config.LEXICAL = "off"

        def restore():
            (config.DB, config.BGE, config.SCHEMA, config.TRANSLATE,
             config.LEXICAL) = old
        self.addCleanup(restore)

        self.assertEqual(config.schema_version(), "v1")
        self.assertEqual(search.search("virumque")["mode"], "fts")
        client = TestClient(main.app)
        self.assertEqual(client.get("/health").json()["schema"], "v1")
        self.assertEqual(client.get("/v1/sources").status_code, 404)


if __name__ == "__main__":
    unittest.main()
