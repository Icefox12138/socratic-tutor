import os
import shutil
import sqlite3
import unittest
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _tmp import mkdtemp  # noqa: E402

from fastapi.testclient import TestClient

from app import config, ingest, main, schema, search
from app.adapters.base import Document, Section, SourceSpec


def _make_v1(path):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, source TEXT, book TEXT,"
                " lang TEXT, page INTEGER, text TEXT, visibility TEXT)")
    con.execute("CREATE VIRTUAL TABLE chunks_fts USING fts5(text, tokenize='unicode61')")
    rows = [
        (1, "library", "a.pdf", "zh", 3, "共同", "tutor"),
        (2, "library", "a.pdf", "zh", 4, "答案是秘密。", "answer_key"),
    ]
    con.executemany("INSERT INTO chunks VALUES (?,?,?,?,?,?,?)", rows)
    con.executemany("INSERT INTO chunks_fts(rowid,text) VALUES (?,?)",
                    [(r[0], r[5]) for r in rows])
    con.commit()
    con.close()


def _make_v2(path):
    schema.ensure_v2(path)
    ingest.ingest(path, Document(
        document_id="wikisource:zh:测试", source_id="wikisource:zh",
        title="测试", lang="zh-classical", license="PD-old", source_version="1",
        sections=[Section(title="甲", text="黃帝者，共同概念：義者宜也。",
                          locator={"scheme": "mediawiki", "site": "x",
                                   "title": "測試", "revision": "1"})]),
        SourceSpec(source_id="wikisource:zh", adapter="mediawiki",
                   base_url="https://example.invalid/w/api.php", license="PD-old"))


class TestFederated(unittest.TestCase):
    def setUp(self):
        self.tmp = mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.v1 = os.path.join(self.tmp, "v1.db")
        self.v2 = os.path.join(self.tmp, "public.db")
        _make_v1(self.v1)
        _make_v2(self.v2)
        self.old = (config.DB, config.SCHEMA, config.BGE, config.TRANSLATE,
                    config.LEXICAL, config.V1_RETRIEVAL, config.V1_DB,
                    config.PUBLIC_DB)
        config.DB, config.SCHEMA, config.BGE = self.v1, "auto", False
        config.TRANSLATE, config.LEXICAL = "off", "off"
        config.V1_RETRIEVAL = False
        config.V1_DB, config.PUBLIC_DB = self.v1, self.v2
        self.addCleanup(self._restore)

    def _restore(self):
        (config.DB, config.SCHEMA, config.BGE, config.TRANSLATE,
         config.LEXICAL, config.V1_RETRIEVAL, config.V1_DB,
         config.PUBLIC_DB) = self.old

    def test_scope_all_merges_both(self):
        out = search.search("共同", scope="all", limit=5)
        self.assertEqual(out["mode"], "federated")
        self.assertEqual(set(out["schemas"]), {"v1", "v2"})
        self.assertGreaterEqual(len(out["results"]), 2)
        self.assertEqual({r["schema"] for r in out["results"]}, {"v1", "v2"})

    def test_scope_all_excludes_answer_key(self):
        out = search.search("秘密", scope="all", limit=5)
        self.assertFalse(any(r.get("page") == 4 for r in out["results"]))

    def test_scope_all_endpoint(self):
        r = TestClient(main.app).get("/v1/search", params={"q": "共同",
                                                           "scope": "all"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["mode"], "federated")

    def test_routed_classical_zh_goes_v2(self):
        out = search.search("黃帝", scope="routed", limit=5)
        self.assertEqual(out["mode"], "routed")
        self.assertEqual(out["routed_to"], "v2")
        self.assertEqual({r["schema"] for r in out["results"]}, {"v2"})

    def test_routed_generic_goes_v1(self):
        out = search.search("共同", scope="routed", limit=5)
        self.assertEqual(out["mode"], "routed")
        self.assertEqual(out["routed_to"], "v1")
        self.assertEqual({r["schema"] for r in out["results"]}, {"v1"})

    def test_routed_endpoint(self):
        r = TestClient(main.app).get("/v1/search", params={"q": "黃帝",
                                                           "scope": "routed"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["routed_to"], "v2")


if __name__ == "__main__":
    unittest.main()
