import json
import os
import shutil
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

from app import config, main, search


def _make_db(path):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, source TEXT, book TEXT,"
                " lang TEXT, page INTEGER, text TEXT, visibility TEXT)")
    con.execute("CREATE VIRTUAL TABLE chunks_fts USING fts5(text, tokenize='unicode61')")
    rows = [
        (1, "library", "b.pdf", "latin", 10, "Arma virumque cano, Troiae qui primus ab oris", "tutor"),
        (2, "library", "b.pdf", "latin", 10, "Italiam fato profugus", "tutor"),
        (3, "library", "b.pdf", "latin", 11, "Musa, mihi causas memora", "tutor"),
    ]
    con.executemany("INSERT INTO chunks VALUES (?,?,?,?,?,?,?)", rows)
    # the index stores tokenised text (lowercase words for Latin), as the schema requires
    import re as _re
    for rid, _src, _book, _lang, _page, text, _vis in rows:
        toks = " ".join(_re.findall(r"[a-z]{2,}", text.lower()))
        con.execute("INSERT INTO chunks_fts (rowid, text) VALUES (?, ?)", (rid, toks))
    con.commit()
    con.close()


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.db = os.path.join(self.tmp, "search.db")
        _make_db(self.db)
        self.old = (config.DB, config.BGE, config.RENDER)
        config.DB, config.BGE = self.db, False
        self.addCleanup(self._restore)

    def _restore(self):
        config.DB, config.BGE, config.RENDER = self.old


class TestRenderSwitch(_Base):
    def test_off_means_no_page_image(self):
        config.RENDER = "off"
        self.assertFalse(config.render_enabled())
        out = search.search("cano", book="b.pdf")
        self.assertIsNone(out["results"][0]["citation"]["page_image"])

    def test_on_means_page_image_present(self):
        config.RENDER = "on"
        self.assertTrue(config.render_enabled())
        out = search.search("cano", book="b.pdf")
        self.assertIn("/v1/pages?", out["results"][0]["citation"]["page_image"])

    def test_pages_endpoint_answers_501_when_off(self):
        config.RENDER = "off"
        r = TestClient(main.app).get("/v1/pages", params={
            "source": "library", "book": "b.pdf", "page": 10})
        self.assertEqual(r.status_code, 501)
        self.assertEqual(r.json()["detail"]["code"], "page_rendering_disabled")

    def test_health_reports_renderer(self):
        config.RENDER = "off"
        body = TestClient(main.app).get("/health").json()
        self.assertEqual(body["render"], "off")


class TestTextVerification(_Base):
    def test_quote_found_across_chunks_on_the_page(self):
        r = TestClient(main.app).get("/v1/verify", params={
            "book": "b.pdf", "page": 10, "quote": "Arma virumque cano"})
        body = r.json()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(body["verified"])
        self.assertEqual(body["method"], "text")

    def test_quote_with_different_punctuation_still_matches(self):
        r = TestClient(main.app).get("/v1/verify", params={
            "book": "b.pdf", "page": 10, "quote": "arma, VIRUMQUE—cano!"})
        self.assertTrue(r.json()["verified"])

    def test_quote_on_the_wrong_page_is_rejected(self):
        r = TestClient(main.app).get("/v1/verify", params={
            "book": "b.pdf", "page": 11, "quote": "Arma virumque cano"})
        self.assertFalse(r.json()["verified"])

    def test_unknown_page_reports_why(self):
        r = TestClient(main.app).get("/v1/verify", params={
            "book": "b.pdf", "page": 999, "quote": "cano"})
        body = r.json()
        self.assertFalse(body["verified"])
        self.assertIn("no text", body["reason"])

    def test_works_with_rendering_off(self):
        config.RENDER = "off"
        r = TestClient(main.app).get("/v1/verify", params={
            "book": "b.pdf", "page": 10, "quote": "Italiam fato profugus"})
        self.assertTrue(r.json()["verified"])


if __name__ == "__main__":
    unittest.main()
