import os
import shutil
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

from app import config, main


class TestNoIndex(unittest.TestCase):
    """A fresh install has no RAG database; the service must stay usable."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.old_db = config.DB
        config.DB = os.path.join(self.tmp, "missing", "search.db")
        self.addCleanup(self._restore)

    def _restore(self):
        config.DB = self.old_db

    def test_health_answers_200_with_reason(self):
        r = TestClient(main.app).get("/health")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["reason"], "no_index")
        self.assertEqual(body["chunks"], 0)
        self.assertIn("RAG-DB-SCHEMA", body["hint"])

    def test_search_reports_no_index_instead_of_crashing(self):
        r = TestClient(main.app).get("/v1/search", params={"q": "test"})
        self.assertEqual(r.status_code, 503)
        detail = r.json()["detail"]
        self.assertEqual(detail["code"], "no_index")


class TestTocSource(unittest.TestCase):
    """The chapter index is data: it must be readable from the RAG database."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.search_db = os.path.join(self.tmp, "search.db")
        con = sqlite3.connect(self.search_db)
        con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, source TEXT, book TEXT,"
                    " lang TEXT, page INTEGER, text TEXT, visibility TEXT)")
        con.commit()
        con.close()
        self.old_db, self.old_in = config.DB, config.TOC_IN
        config.DB = self.search_db
        config.TOC_IN = "search"          # read toc from the RAG db, not state.db
        self.addCleanup(self._restore)

    def _restore(self):
        config.DB, config.TOC_IN = self.old_db, self.old_in

    def test_toc_round_trips_through_the_rag_db(self):
        from app import toc
        chapters = [{"ord": 0, "level": 1, "title": "卷1", "page_start": 1, "page_end": 9,
                     "volume": 1}]
        toc.save("library", "b.pdf", chapters)
        rows = toc.load("library", "b.pdf")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "卷1")
        # the rows must have landed in the RAG db, not in state.db
        con = sqlite3.connect(self.search_db)
        n = con.execute("SELECT count(*) FROM toc").fetchone()[0]
        con.close()
        self.assertEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
