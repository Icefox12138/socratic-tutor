import os
import shutil
import tempfile
import unittest

from app import config, ingest, schema, search, translate
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


class TestV2TranslationSearch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.db = os.path.join(self.tmp, "public.db")
        schema.ensure_v2(self.db)

        ingest.ingest(self.db, _doc(
            "wikisource:zh:史記/卷001", "wikisource:zh", "史記/卷001",
            "zh-classical", "黃帝",
            "黃帝者，少典之子，姓公孫，名曰軒轅。",
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

        self.old = (config.DB, config.BGE, config.SCHEMA, config.TRANSLATE,
                    config.LEXICAL)
        config.DB, config.BGE, config.SCHEMA = self.db, False, "auto"
        config.TRANSLATE = "glossary"
        config.LEXICAL = "off"
        translate.clear_cache()
        self.addCleanup(self._restore)

    def _restore(self):
        (config.DB, config.BGE, config.SCHEMA, config.TRANSLATE,
         config.LEXICAL) = self.old
        translate.clear_cache()

    def test_chinese_question_reaches_greek_passage(self):
        out = search.search("阿喀琉斯的愤怒")
        self.assertTrue(out["translated"])
        self.assertTrue(out["translations"])
        self.assertEqual(out["results"][0]["document_id"],
                         "urn:cts:greekLit:tlg0012.tlg001.perseus-grc1")
        self.assertEqual(out["results"][0]["citation"]["scheme"], "cts")
        langs = {v["lang"] for v in out["translations"]}
        self.assertIn("greek", langs)

    def test_chinese_alias_reaches_traditional_section(self):
        out = search.search("黄帝的出身")
        self.assertTrue(out["translated"])
        self.assertEqual(out["results"][0]["document_id"],
                         "wikisource:zh:史記/卷001")
        self.assertEqual(out["results"][0]["section"], "黃帝")

    def test_translation_off_does_not_expand(self):
        config.TRANSLATE = "off"
        translate.clear_cache()
        out = search.search("黄帝的出身")
        self.assertFalse(out["translated"])
        self.assertEqual(out["results"], [])

    def test_translation_payload_shape(self):
        out = search.search("特洛伊战争")
        self.assertIsInstance(out["translations"], list)
        for item in out["translations"]:
            self.assertIn("lang", item)
            self.assertIn("text", item)
            self.assertIn("source", item)


if __name__ == "__main__":
    unittest.main()
