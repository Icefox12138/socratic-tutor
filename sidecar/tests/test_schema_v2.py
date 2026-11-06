import os
import shutil
import sqlite3
import tempfile
import unittest

from app import schema


class TestV2Schema(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.db = os.path.join(self.tmp, "public.db")

    def test_ensure_is_idempotent_and_stamps_version(self):
        schema.ensure_v2(self.db)
        schema.ensure_v2(self.db)
        self.assertEqual(schema.version(self.db), "v2")
        con = sqlite3.connect(self.db)
        try:
            row = con.execute("SELECT value FROM schema_meta WHERE key='rag_schema'").fetchone()
            self.assertEqual(row[0], "v2")
            cols = {r[1] for r in con.execute("PRAGMA table_info(chunks)")}
            self.assertIn("document_id", cols)
            self.assertIn("locator_json", cols)
            self.assertIn("stream", cols)
            tables = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            for name in ("sources", "documents", "chunks", "chunks_fts", "assets", "embeddings"):
                self.assertIn(name, tables)
        finally:
            con.close()

    def test_v1_catalogue_is_still_recognised(self):
        con = sqlite3.connect(self.db)
        con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, source TEXT, book TEXT,"
                    " lang TEXT, page INTEGER, text TEXT, visibility TEXT)")
        con.commit()
        con.close()
        self.assertEqual(schema.version(self.db), "v1")

    def test_missing_and_unknown(self):
        self.assertEqual(schema.version(os.path.join(self.tmp, "nope.db")), "none")
        other = os.path.join(self.tmp, "other.db")
        con = sqlite3.connect(other)
        con.execute("CREATE TABLE unrelated (x)")
        con.commit()
        con.close()
        self.assertEqual(schema.version(other), "unknown")

    def test_counts_reports_documents_and_sources(self):
        schema.ensure_v2(self.db)
        con = sqlite3.connect(self.db)
        con.execute("INSERT INTO sources(source_id, adapter) VALUES('s', 'mediawiki')")
        con.execute("INSERT INTO documents(document_id, source_id, title) VALUES('d', 's', 't')")
        con.commit()
        con.close()
        self.assertEqual(schema.counts(self.db),
                         {"chunks": 0, "documents": 1, "sources": 1})


class TestLocators(unittest.TestCase):
    def test_mediawiki_url_pins_revision(self):
        from app import locators
        loc = {"scheme": "mediawiki", "site": "zh.wikisource.org",
               "title": "史記/卷001", "revision": "123", "section": "黃帝"}
        url = locators.url(loc)
        self.assertIn("zh.wikisource.org/wiki/", url)
        self.assertIn("oldid=123", url)
        self.assertIn("%E9%BB%83%E5%B8%9D", url)

    def test_cts_url_and_label(self):
        from app import locators
        loc = {"scheme": "cts", "urn": "urn:cts:greekLit:tlg0012.tlg001.perseus-grc1:1.1",
               "book": "1", "line_start": 1, "line_end": 1}
        self.assertIn("scaife.perseus.org/reader/urn:cts:", locators.url(loc))
        self.assertEqual(locators.default_label(loc, {"title": "Iliad"}),
                         "Iliad 1.1")

    def test_validate_requires_revision(self):
        from app import locators
        locators.validate({"scheme": "mediawiki", "site": "x", "title": "y",
                           "revision": "1"})
        with self.assertRaises(locators.LocatorError):
            locators.validate({"scheme": "mediawiki", "site": "x", "title": "y"})
        with self.assertRaises(locators.LocatorError):
            locators.validate({"scheme": "nonsense"})


class TestTextUtil(unittest.TestCase):
    def test_tokens_v2_folds_greek_and_latin_accents(self):
        from app import textutil
        toks = textutil.tokens_v2("μῆνιν ἄειδε Troiae confectō")
        self.assertIn("μηνιν", toks)
        self.assertIn("troiae", toks)
        self.assertIn("confecto", toks)
        # θεὰ (grave) and θεά (acute) must collide
        self.assertEqual(textutil.tokens_v2("θεὰ"), textutil.tokens_v2("θεά"))
        self.assertIn("θεα", textutil.tokens_v2("θεά"))
        # final sigma folds too
        self.assertEqual(textutil.tokens_v2("θεός"), textutil.tokens_v2("θεὸς"))

    def test_v1_tokens_unchanged(self):
        from app import textutil
        self.assertEqual(textutil.tokens("Arma virumque"), ["arma", "virumque"])

    def test_chunk_offsets_point_into_the_section(self):
        from app import textutil
        text = "第一段。" * 40 + "\n\n" + "第二段。" * 40
        chunks = textutil.chunk_paragraphs(text, max_chars=100)
        self.assertGreater(len(chunks), 2)
        for piece, start, end in chunks:
            self.assertEqual(text[start:end], piece)


if __name__ == "__main__":
    unittest.main()
