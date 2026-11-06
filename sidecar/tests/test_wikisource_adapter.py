import unittest

from app.adapters.base import FetchError
from app.adapters.wikisource import WikisourceAdapter, extract_sections

HTML = """
<div class="mw-parser-output">
<style>.x{color:red}</style>
<table class="ws-header"><tr><td>導航 ◄ 卷一</td></tr></table>
<p>序言 &amp; 說明。</p>
<div class="mw-heading mw-heading2"><h2 id="one">第一章</h2>
<span class="mw-editsection">[<a href="/edit">编辑</a>]</span></div>
<p>道可道，非常道。</p>
<p>名可名，非常名。<sup class="reference">[1]</sup></p>
<h2>第二章</h2>
<p>天下皆知美之為美。</p>
</div>
"""


def fake_parse(url, params=None, **kwargs):
    assert params["action"] == "parse"
    return {"parse": {"title": "測試/卷一", "pageid": 9, "revid": 123,
                      "text": HTML}}


class TestExtractSections(unittest.TestCase):
    def test_headings_and_text(self):
        sections = extract_sections(HTML)
        self.assertEqual([h for h, _t in sections], ["", "第一章", "第二章"])
        self.assertIn("序言 & 說明", sections[0][1])

    def test_navigation_edit_links_and_references_are_removed(self):
        text = "".join(t for _h, t in extract_sections(HTML))
        self.assertNotIn("導航", text)
        self.assertNotIn("编辑", text)
        self.assertNotIn("[1]", text)
        self.assertNotIn("color:red", text)
        self.assertIn("道可道，非常道。", text)

    def test_empty_html(self):
        self.assertEqual(extract_sections(""), [])


class TestWikisourceAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = WikisourceAdapter(lang="zh", license="PD-old",
                                        min_interval=0, opener=fake_parse)

    def test_document_and_locators(self):
        doc = self.adapter.fetch("測試/卷一")
        self.assertEqual(doc.document_id, "wikisource:zh:測試/卷一")
        self.assertEqual(doc.source_id, "wikisource:zh")
        self.assertEqual(doc.source_version, "123")
        self.assertEqual(doc.lang, "zh-classical")
        self.assertEqual(doc.license, "PD-old")
        self.assertEqual(len(doc.sections), 3)
        for section in doc.sections:
            self.assertEqual(section.locator["scheme"], "mediawiki")
            self.assertEqual(section.locator["revision"], "123")
            self.assertEqual(section.locator["site"], "zh.wikisource.org")
        self.assertEqual(doc.sections[1].locator["section"], "第一章")
        self.assertIn("oldid=123", doc.canonical_url)

    def test_missing_page_is_a_fetch_error(self):
        def missing(url, params=None, **kwargs):
            return {"error": {"code": "missingtitle", "info": "no such page"}}

        adapter = WikisourceAdapter(lang="zh", min_interval=0, opener=missing)
        with self.assertRaises(FetchError):
            adapter.fetch("不存在")

    def test_source_spec_names_adapter_and_licence(self):
        spec = self.adapter.source()
        self.assertEqual(spec.source_id, "wikisource:zh")
        self.assertEqual(spec.adapter, "mediawiki")
        self.assertEqual(spec.license, "PD-old")
        self.assertEqual(spec.redistribution, "share-alike")
        self.assertIn("zh.wikisource.org", spec.base_url)

    def test_search_titles(self):
        def searcher(url, params=None, **kwargs):
            self.assertEqual(params["list"], "search")
            return {"query": {"search": [{"title": "史記/卷001"}]}}

        adapter = WikisourceAdapter(lang="zh", min_interval=0, opener=searcher)
        self.assertEqual(adapter.search("史記"), ["史記/卷001"])

    def test_language_codes_map_to_project_names(self):
        latin = WikisourceAdapter(lang="la", min_interval=0, opener=fake_parse)
        self.assertEqual(latin.fetch("Aeneis").lang, "latin")
        greek = WikisourceAdapter(lang="el", min_interval=0, opener=fake_parse)
        self.assertEqual(greek.fetch("Ilias").lang, "greek")


if __name__ == "__main__":
    unittest.main()
