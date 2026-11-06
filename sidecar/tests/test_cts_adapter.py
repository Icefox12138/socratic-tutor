import unittest

from app.adapters.base import FetchError
from app.adapters.cts import CtsAdapter, passage, work_urn

XML = """<?xml version="1.0" encoding="UTF-8"?>
<cts:GetPassage xmlns:cts="http://chs.harvard.edu/xmlns/cts3"
                xmlns:tei="http://www.tei-c.org/ns/1.0">
  <cts:request>
    <cts:workUrn>urn:cts:greekLit:tlg0012.tlg001.perseus-grc1</cts:workUrn>
    <cts:groupname>Homer</cts:groupname>
    <cts:title>Iliad</cts:title>
    <cts:versionInfo>Perseus 4.0</cts:versionInfo>
  </cts:request>
  <cts:reply>
    <tei:TEI>
      <tei:text xml:lang="grc">
        <tei:body>
          <tei:div type="line"><milestone ed="P" unit="para"/>{text}</tei:div>
        </tei:body>
      </tei:text>
    </tei:TEI>
  </cts:reply>
</cts:GetPassage>
"""

ERROR_XML = """<?xml version="1.0" encoding="UTF-8"?>
<cts:GetPassage xmlns:cts="http://chs.harvard.edu/xmlns/cts3">
  <cts:reply name="CTSError"><cts:msg>no such passage</cts:msg></cts:reply>
</cts:GetPassage>
"""


def opener(url, params=None, **kwargs):
    urn = params["urn"]
    text = "μῆνιν ἄειδε θεὰ" if urn.endswith(":1.1") else "οὐλομένην"
    return XML.format(text=text).encode("utf-8"), "text/xml"


class TestCtsAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = CtsAdapter(min_interval=0, opener=opener)

    def test_fetch_reads_tei_and_request_metadata(self):
        doc = self.adapter.fetch("urn:cts:greekLit:tlg0012.tlg001.perseus-grc1:1.1")
        self.assertEqual(doc.document_id, "urn:cts:greekLit:tlg0012.tlg001.perseus-grc1")
        self.assertEqual(doc.title, "Iliad")
        self.assertEqual(doc.author, "Homer")
        self.assertEqual(doc.lang, "greek")
        self.assertEqual(doc.edition, "Perseus 4.0")
        self.assertEqual(len(doc.sections), 1)
        loc = doc.sections[0].locator
        self.assertEqual(loc["scheme"], "cts")
        self.assertEqual(loc["book"], "1")
        self.assertEqual(loc["line_start"], 1)
        self.assertIn("μῆνιν", doc.sections[0].text)
        self.assertIn("scaife.perseus.org/reader/urn:cts:", doc.canonical_url)

    def test_fetch_many_merges_passages(self):
        doc = self.adapter.fetch_many([
            "urn:cts:greekLit:tlg0012.tlg001.perseus-grc1:1.1",
            "urn:cts:greekLit:tlg0012.tlg001.perseus-grc1:1.2",
        ])
        self.assertEqual(len(doc.sections), 2)
        self.assertEqual([s.ordinal for s in doc.sections], [0, 1])
        self.assertIn("οὐλομένην", doc.sections[1].text)

    def test_fetch_many_can_skip_refused_lines(self):
        def flaky(url, params=None, **kwargs):
            urn = params["urn"]
            if urn.endswith(":1.2"):
                return ERROR_XML.encode("utf-8"), "text/xml"
            return XML.format(text="μῆνιν ἄειδε θεὰ").encode("utf-8"), "text/xml"

        adapter = CtsAdapter(min_interval=0, opener=flaky)
        doc = adapter.fetch_many([
            "urn:cts:greekLit:tlg0012.tlg001.perseus-grc1:1.1",
            "urn:cts:greekLit:tlg0012.tlg001.perseus-grc1:1.2",
            "urn:cts:greekLit:tlg0012.tlg001.perseus-grc1:1.3",
        ], skip_errors=True)
        self.assertEqual(len(doc.sections), 2)
        self.assertEqual(len(doc.metadata["skipped"]), 1)
        with self.assertRaises(FetchError):
            adapter.fetch_many([
                "urn:cts:greekLit:tlg0012.tlg001.perseus-grc1:1.1",
                "urn:cts:greekLit:tlg0012.tlg001.perseus-grc1:1.2",
            ])

    def test_cts_error_is_reported(self):
        def broken(url, params=None, **kwargs):
            return ERROR_XML.encode("utf-8"), "text/xml"

        adapter = CtsAdapter(min_interval=0, opener=broken)
        with self.assertRaises(FetchError):
            adapter.fetch("urn:cts:greekLit:tlg0012.tlg001.perseus-grc1:9.9")

    def test_non_urn_is_rejected(self):
        with self.assertRaises(FetchError):
            self.adapter.fetch("Perseus:text:1999.01.0134")

    def test_urn_helpers(self):
        urn = "urn:cts:greekLit:tlg0012.tlg001.perseus-grc1:1.10-1.20"
        self.assertEqual(work_urn(urn),
                         "urn:cts:greekLit:tlg0012.tlg001.perseus-grc1")
        self.assertEqual(passage(urn), ("1", 10, 20))
        self.assertEqual(passage("urn:cts:greekLit:tlg0012.tlg001.perseus-grc1"),
                         (None, None, None))


if __name__ == "__main__":
    unittest.main()
