import os
import shutil
import sqlite3
import unittest
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _tmp import mkdtemp  # noqa: E402

import numpy as np
try:
    import torch
except ImportError:  # optional GPU/CPU test dependency
    torch = None

from app import config, ingest, schema, search, textutil
from app.adapters.base import Document, Section, SourceSpec


class FakeST:
    def __init__(self, vector):
        self.vector = np.asarray([vector], dtype=np.float32)

    def encode(self, texts, **kwargs):
        return self.vector


def fake_b(rows, ids, vecs, query_vec):
    return {
        "device": "cpu",
        "st": FakeST(query_vec),
        "tok": None,
        "rer": None,
        "ids": np.asarray(ids, dtype=np.int64),
        "vecs": torch.tensor(vecs, dtype=torch.float32),
        "meta": {r["id"]: r for r in rows},
        "texts": {r["id"]: r["text"] for r in rows},
    }


def make_doc(document_id, title, lang, text, source_id):
    return Document(
        document_id=document_id, source_id=source_id, title=title, lang=lang,
        license="PD-old", source_version="1",
        sections=[Section(title="一", text=text, locator={
            "scheme": "mediawiki", "site": "example.invalid", "title": title,
            "revision": "1", "section": "一"})])


def spec(source_id):
    return SourceSpec(source_id=source_id, adapter="mediawiki",
                      base_url="https://example.invalid/w/api.php", license="PD-old")


@unittest.skipUnless(torch is not None, "torch not installed")
class TestV2Vectors(unittest.TestCase):
    def setUp(self):
        self.orig_load = search._load_v2_bge
        self.orig_rerank = search._v2_rerank
        self.orig_v2 = (search._V2_BGE, search._V2_BGE_ERR)

        self.tmp = mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.db = os.path.join(self.tmp, "public.db")
        schema.ensure_v2(self.db)
        ingest.ingest(self.db, make_doc("wikisource:zh:甲", "甲", "zh-classical",
                                        "道可道，非常道。", "wikisource:zh"),
                      spec("wikisource:zh"))
        ingest.ingest(self.db, make_doc("wikisource:la:乙", "乙", "latin",
                                        "Arma virumque cano.", "wikisource:la"),
                      spec("wikisource:la"))
        self.commentary = self._insert("注釋：道不可言說。", stream="commentary")
        self.secret = self._insert("答案：非常道。", visibility="answer_key")
        self.rows = self._chunk_rows()
        self.vecs = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)

        self.old = (config.DB, config.BGE, config.SCHEMA, config.TRANSLATE,
                    config.LEXICAL, config.BGE_V2_VECTORS, config.BGE_V2_IDS)
        config.DB, config.BGE, config.SCHEMA = self.db, True, "auto"
        config.TRANSLATE = "off"
        config.LEXICAL = "off"
        self.addCleanup(self._restore)

    def _restore(self):
        (config.DB, config.BGE, config.SCHEMA, config.TRANSLATE,
         config.LEXICAL, config.BGE_V2_VECTORS, config.BGE_V2_IDS) = self.old
        search._V2_BGE, search._V2_BGE_ERR = self.orig_v2
        search._v2_rerank = self.orig_rerank
        search._load_v2_bge = self.orig_load

    def _insert(self, text, stream="text", visibility="tutor"):
        con = sqlite3.connect(self.db)
        try:
            cur = con.execute(
                "INSERT INTO chunks(document_id, ordinal, section, text, lang,"
                " stream, visibility, locator_json, citation_label, quality)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                ("wikisource:zh:甲", 99, "補編", text, "zh-classical", stream,
                 visibility, '{"scheme":"mediawiki","site":"example.invalid",'
                 '"title":"甲","revision":"1","section":"補編"}', "補編", "t"))
            con.execute("INSERT INTO chunks_fts(rowid, text) VALUES(?, ?)",
                        (cur.lastrowid, " ".join(textutil.tokens_v2(text))))
            con.commit()
            return cur.lastrowid
        finally:
            con.close()

    def _chunk_rows(self):
        con = sqlite3.connect(self.db)
        con.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in con.execute(search._V2_CHUNK_SQL)]
        finally:
            con.close()

    def _install(self, query_vec=(1, 0, 0)):
        ids = [r["id"] for r in self.rows]
        b = fake_b(self.rows, ids, self.vecs, query_vec)
        search._V2_BGE = b
        search._V2_BGE_ERR = None
        search._load_v2_bge = lambda: b
        search._v2_rerank = lambda _b, _q, pairs: [
            (cid, 1.0 - i * 0.1) for i, (cid, _text) in enumerate(pairs)]
        return b

    def test_hybrid_uses_bge_when_fts_is_empty(self):
        self._install()
        out = search.search("semantic-only", view="student")
        self.assertEqual(out["mode"], "bge+rerank-public")
        self.assertTrue(out["results"])
        self.assertEqual(out["results"][0]["document_id"], "wikisource:zh:甲")
        self.assertEqual(out["results"][0]["citation"]["scheme"], "mediawiki")

    def test_student_never_sees_commentary_or_answer_key(self):
        self._install(query_vec=(0, 0, 1))
        student = [r["chunk_id"] for r in
                   search.search("semantic-only", view="student")["results"]]
        self.assertNotIn(self.commentary, student)
        self.assertNotIn(self.secret, student)
        tutor = [r["chunk_id"] for r in
                 search.search("semantic-only", view="tutor")["results"]]
        self.assertIn(self.commentary, tutor)
        self.assertNotIn(self.secret, tutor)

    def test_filters_apply_to_bge_candidates(self):
        self._install()
        out = search.search("semantic-only", source="wikisource:la")
        self.assertEqual([r["document_id"] for r in out["results"]],
                         ["wikisource:la:乙"])

    def test_loader_failure_falls_back_to_fts(self):
        search._V2_BGE = None
        search._V2_BGE_ERR = "model missing"
        out = search.search("道可道")
        self.assertEqual(out["mode"], "fts-public")
        self.assertTrue(out["results"])

    def test_health_reports_v2_vectors(self):
        self._install()
        body = search.health()
        self.assertEqual(body["bge"], "ready")
        self.assertEqual(body["vectors"], config.BGE_V2_VECTORS)
        config.BGE = False
        self.assertEqual(search.v2_bge_status(), "disabled")

    def test_missing_vectors_are_reported_not_crashed(self):
        search._V2_BGE = None
        search._V2_BGE_ERR = None
        config.BGE_V2_VECTORS = os.path.join(self.tmp, "nope.npy")
        config.BGE_V2_IDS = os.path.join(self.tmp, "nope-ids.npy")
        config.BGE = True
        self.assertTrue(search.v2_bge_status().startswith("missing: "))
        out = search.search("道可道")
        self.assertEqual(out["mode"], "fts-public")


if __name__ == "__main__":
    unittest.main()
