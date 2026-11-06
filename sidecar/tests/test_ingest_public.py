import contextlib
import io
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from argparse import Namespace

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "sidecar"))

import ingest_public                                    # noqa: E402
from app import ingest, schema                          # noqa: E402
from app.adapters.base import Document, Section, SourceSpec  # noqa: E402


def doc(text="道可道，非常道。", revision="42"):
    return Document(
        document_id="wikisource:zh:道德經", source_id="wikisource:zh",
        title="道德經", lang="zh-classical", license="PD-old",
        source_version=revision,
        canonical_url="https://zh.wikisource.org/wiki/道德經?oldid=%s" % revision,
        sections=[Section(title="第一章", text=text, locator={
            "scheme": "mediawiki", "site": "zh.wikisource.org",
            "title": "道德經", "revision": revision, "section": "第一章"})])


class FakeAdapter:
    def __init__(self, document):
        self.document = document
        self.fetched = []

    def source(self):
        return SourceSpec(source_id="wikisource:zh", adapter="mediawiki",
                          base_url="https://zh.wikisource.org/w/api.php",
                          license="PD-old", redistribution="share-alike",
                          rate_limit=1.0)

    def fetch(self, title, **kwargs):
        self.fetched.append(title)
        return self.document

    def search(self, query, limit=10):
        return []


def args(db, **over):
    base = dict(source="wikisource", lang="zh", db=db, title=["道德經"],
                titles_file=None, query=None, search_limit=10, urn=None,
                work_title=None, author=None, edition=None, license="PD-old",
                rate=0.0, chunk_chars=1200, dry_run=False, skip_errors=False)
    base.update(over)
    return Namespace(**base)


class TestIngest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.db = os.path.join(self.tmp, "public.db")

    def _count(self, sql, params=()):
        con = sqlite3.connect(self.db)
        try:
            return con.execute(sql, params).fetchone()[0]
        finally:
            con.close()

    def test_ingest_writes_source_document_chunks_and_fts(self):
        stats = ingest.ingest(self.db, doc(), FakeAdapter(doc()).source())
        self.assertEqual(stats["chunks"], 1)
        self.assertEqual(schema.version(self.db), "v2")
        self.assertEqual(self._count("SELECT count(*) FROM sources"), 1)
        self.assertEqual(self._count("SELECT count(*) FROM documents"), 1)
        self.assertEqual(self._count("SELECT count(*) FROM chunks"), 1)
        self.assertEqual(self._count("SELECT count(*) FROM chunks_fts"), 1)
        con = sqlite3.connect(self.db)
        label = con.execute("SELECT citation_label FROM chunks").fetchone()[0]
        con.close()
        self.assertIn("《道德經》", label)
        self.assertIn("rev 42", label)

    def test_reingest_replaces_instead_of_duplicating(self):
        adapter = FakeAdapter(doc())
        ingest.ingest(self.db, adapter.document, adapter.source())
        ingest.ingest(self.db, adapter.document, adapter.source())
        self.assertEqual(self._count("SELECT count(*) FROM chunks"), 1)
        self.assertEqual(self._count("SELECT count(*) FROM chunks_fts"), 1)

        # a revision with different text must not leave the old text behind
        newer = doc(text="上善若水。", revision="43")
        ingest.ingest(self.db, newer, adapter.source())
        self.assertEqual(self._count("SELECT count(*) FROM chunks"), 1)
        con = sqlite3.connect(self.db)
        texts = [r[0] for r in con.execute("SELECT text FROM chunks")]
        con.close()
        self.assertEqual(texts, ["上善若水。"])

    def test_ingest_rejects_a_document_without_sections(self):
        empty = doc()
        empty.sections = []
        with self.assertRaises(ValueError):
            ingest.ingest(self.db, empty, FakeAdapter(doc()).source())


class TestCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.db = os.path.join(self.tmp, "public.db")

    def _run(self, ns, adapter):
        with contextlib.redirect_stdout(io.StringIO()):
            return ingest_public.run(ns, adapter=adapter)

    def test_dry_run_writes_nothing(self):
        adapter = FakeAdapter(doc())
        result = self._run(args(self.db, dry_run=True), adapter)
        self.assertTrue(result[0]["dry_run"])
        self.assertFalse(os.path.exists(self.db))
        self.assertEqual(adapter.fetched, ["道德經"])

    def test_run_ingests_and_reports(self):
        adapter = FakeAdapter(doc())
        result = self._run(args(self.db), adapter)
        self.assertEqual(result[0]["chunks"], 1)
        self.assertEqual(schema.version(self.db), "v2")
        con = sqlite3.connect(self.db)
        n = con.execute("SELECT count(*) FROM sources").fetchone()[0]
        con.close()
        self.assertEqual(n, 1)

    def test_refuses_to_write_v2_into_a_v1_catalogue(self):
        con = sqlite3.connect(self.db)
        con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, source TEXT, book TEXT,"
                    " lang TEXT, page INTEGER, text TEXT, visibility TEXT)")
        con.commit()
        con.close()
        with self.assertRaises(SystemExit):
            self._run(args(self.db), FakeAdapter(doc()))

    def test_parser_defaults(self):
        parsed = ingest_public.build_parser().parse_args([
            "--source", "wikisource", "--title", "史記/卷001"])
        self.assertEqual(parsed.title, ["史記/卷001"])
        self.assertEqual(parsed.rate, 1.0)


if __name__ == "__main__":
    unittest.main()
