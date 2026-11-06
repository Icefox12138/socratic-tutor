import os
import shutil
import sqlite3
import sys
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _tmp import mkdtemp  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "sidecar"))

import embed_public                                   # noqa: E402
from app import ingest, schema                        # noqa: E402
from app.adapters.base import Document, Section, SourceSpec  # noqa: E402


class FakeEncoder:
    def __init__(self, dim=4):
        self.dim = dim
        self.calls = []

    def encode(self, texts, **kwargs):
        self.calls.append(list(texts))
        out = []
        for text in texts:
            v = [0.0] * self.dim
            v[0] = 1.0
            v[1] = float(len(text) % 7 + 1)
            out.append(v)
        return np.asarray(out, dtype=np.float32)


def make_doc(text, document_id="wikisource:zh:甲", revision="1"):
    return Document(
        document_id=document_id, source_id="wikisource:zh", title="甲",
        lang="zh-classical", license="PD-old", source_version=revision,
        sections=[Section(title="一", text=text, locator={
            "scheme": "mediawiki", "site": "zh.wikisource.org",
            "title": "甲", "revision": revision, "section": "一"})])


def spec():
    return SourceSpec(source_id="wikisource:zh", adapter="mediawiki",
                      base_url="https://zh.wikisource.org/w/api.php",
                      license="PD-old")


class TestEmbedPublic(unittest.TestCase):
    def setUp(self):
        self.tmp = mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.db = os.path.join(self.tmp, "public.db")
        self.vec = os.path.join(self.tmp, "vectors", "public-vectors.npy")
        self.ids = os.path.join(self.tmp, "vectors", "public-ids.npy")
        schema.ensure_v2(self.db)
        ingest.ingest(self.db, make_doc("道可道，非常道。"), spec())
        ingest.ingest(self.db, make_doc("上善若水。", "wikisource:zh:乙", "2"), spec())

    def _chunk_ids(self):
        con = sqlite3.connect(self.db)
        try:
            return [r[0] for r in con.execute("SELECT id FROM chunks ORDER BY id")]
        finally:
            con.close()

    def test_builds_aligned_vectors_and_embeddings_rows(self):
        stats = embed_public.embed_chunks(
            self.db, self.vec, self.ids, FakeEncoder(), model_name="fake",
            version="test")
        self.assertEqual(stats["chunks"], 2)
        self.assertEqual(stats["embedded"], 2)
        self.assertEqual(stats["dim"], 4)
        vecs = np.load(self.vec)
        ids = np.load(self.ids)
        self.assertEqual(vecs.shape, (2, 4))
        self.assertEqual(ids.tolist(), self._chunk_ids())
        self.assertTrue(np.allclose(np.linalg.norm(vecs, axis=1), 1.0, atol=1e-3))
        con = sqlite3.connect(self.db)
        try:
            rows = con.execute(
                "SELECT chunk_id, model, dim, version FROM embeddings ORDER BY chunk_id"
            ).fetchall()
        finally:
            con.close()
        self.assertEqual([r[0] for r in rows], self._chunk_ids())
        self.assertEqual({r[1] for r in rows}, {"fake"})
        self.assertEqual({r[2] for r in rows}, {4})

    def test_incremental_reuses_existing_and_prunes_orphans(self):
        encoder = FakeEncoder()
        embed_public.embed_chunks(self.db, self.vec, self.ids, encoder)
        before = np.load(self.vec).copy()

        ingest.ingest(self.db, make_doc("天下皆知美之為美。", "wikisource:zh:丙", "3"),
                      spec())
        stats = embed_public.embed_chunks(self.db, self.vec, self.ids, FakeEncoder())
        self.assertEqual(stats["embedded"], 1)
        self.assertEqual(stats["reused"], 2)
        after = np.load(self.vec)
        self.assertEqual(after.shape[0], 3)
        # The two old rows kept their exact vectors.
        np.testing.assert_allclose(after[:2], before[:2])

        # Deleting a document must drop its vector, not leave an orphan id.
        con = sqlite3.connect(self.db)
        con.execute("DELETE FROM chunks_fts WHERE rowid IN "
                    "(SELECT id FROM chunks WHERE document_id='wikisource:zh:丙')")
        con.execute("DELETE FROM chunks WHERE document_id='wikisource:zh:丙'")
        con.commit()
        con.close()
        stats = embed_public.embed_chunks(self.db, self.vec, self.ids, FakeEncoder())
        self.assertEqual(stats["chunks"], 2)
        self.assertEqual(np.load(self.ids).tolist(), self._chunk_ids())

    def test_rebuild_reencodes_everything(self):
        embed_public.embed_chunks(self.db, self.vec, self.ids, FakeEncoder())
        stats = embed_public.embed_chunks(self.db, self.vec, self.ids,
                                          FakeEncoder(), rebuild=True)
        self.assertEqual(stats["embedded"], 2)
        self.assertEqual(stats["reused"], 0)

    def test_limit_does_not_drop_existing_vectors(self):
        embed_public.embed_chunks(self.db, self.vec, self.ids, FakeEncoder())
        embed_public.embed_chunks(self.db, self.vec, self.ids, FakeEncoder(),
                                  limit=1)
        self.assertEqual(np.load(self.vec).shape[0], 2)

    def test_bad_vector_file_shape_is_rejected(self):
        os.makedirs(os.path.dirname(self.vec), exist_ok=True)
        np.save(self.vec, np.zeros((2, 4), dtype=np.float16))
        np.save(self.ids, np.array([1], dtype=np.int64))
        with self.assertRaises(ValueError):
            embed_public._load_existing(self.vec, self.ids)

    def test_rejects_a_v1_catalogue(self):
        v1 = os.path.join(self.tmp, "v1.db")
        con = sqlite3.connect(v1)
        con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, source TEXT, book TEXT,"
                    " lang TEXT, page INTEGER, text TEXT, visibility TEXT)")
        con.commit()
        con.close()
        with self.assertRaises(ValueError):
            embed_public.embed_chunks(v1, self.vec, self.ids, FakeEncoder())

    def test_rebuild_and_limit_cannot_be_combined(self):
        with self.assertRaises(ValueError):
            embed_public.embed_chunks(self.db, self.vec, self.ids, FakeEncoder(),
                                      rebuild=True, limit=1)


if __name__ == "__main__":
    unittest.main()
