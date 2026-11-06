import unittest

from app import config, translate


class TestGlossary(unittest.TestCase):
    def setUp(self):
        self.old = config.TRANSLATE
        config.TRANSLATE = "glossary"
        translate.clear_cache()
        self.addCleanup(self._restore)

    def _restore(self):
        config.TRANSLATE = self.old
        translate.clear_cache()

    def _by_lang(self, variants):
        return {v["lang"]: v for v in variants}

    def test_chinese_myth_terms_expand_to_greek_and_latin(self):
        got = self._by_lang(translate.expand(
            "阿喀琉斯的愤怒", targets={"greek", "latin"}))
        self.assertIn("μῆνιν", got["greek"]["text"])
        self.assertIn("Ἀχιλῆος", got["greek"]["text"])
        self.assertIn("ira", got["latin"]["text"])
        self.assertEqual(got["greek"]["source"], "glossary")

    def test_chinese_alias_expands_to_traditional(self):
        got = translate.expand("黄帝的出身", targets={"zh-classical"})
        self.assertEqual(len(got), 1)
        self.assertIn("黃帝", got[0]["text"])
        self.assertIn("少典之子", got[0]["text"])

    def test_off_returns_nothing(self):
        config.TRANSLATE = "off"
        self.assertEqual(translate.expand("阿喀琉斯的愤怒", targets={"greek"}), [])

    def test_ascii_keys_use_word_boundaries(self):
        # "warm" must not match the "war" entry.
        self.assertEqual(translate.expand("warm", targets={"latin"}), [])

    def test_target_order_is_deterministic(self):
        # targets is a set at the call site; expansion order must not depend on
        # hash randomisation or RRF ties become non-reproducible.
        got = translate.expand("阿喀琉斯的愤怒", targets={"latin", "greek"})
        self.assertEqual([v["lang"] for v in got], ["greek", "latin"])

    def test_oov_detection_known_and_unknown(self):
        self.assertEqual(translate.oov_terms("阿喀琉斯的愤怒"), [])
        self.assertEqual(translate.oov_terms("黄帝的出身"), [])
        self.assertTrue(translate.oov_terms("克鲁塞斯"))
        self.assertTrue(translate.oov_terms("银弓之神"))
        self.assertTrue(translate.oov_terms("Chryses"))
        self.assertFalse(translate.oov_terms("Achilles"))
        # Chinese-history questions are a domain gate: never sent to the LLM.
        self.assertFalse(translate.needs_llm("周文王为什么被囚禁在羑里"))
        self.assertTrue(translate.needs_llm("克鲁塞斯"))

    def test_auto_calls_llm_only_for_oov(self):
        calls = []
        old_mode, old_llm = config.TRANSLATE, translate.llm_expand
        config.TRANSLATE = "auto"

        def fake_llm(query, targets):
            calls.append(query)
            return [{"lang": "greek", "text": "Χρύσης", "source": "llm"}]

        translate.llm_expand = fake_llm
        self.addCleanup(lambda: setattr(config, "TRANSLATE", old_mode))
        self.addCleanup(lambda: setattr(translate, "llm_expand", old_llm))
        translate.clear_cache()
        translate.expand("阿喀琉斯的愤怒", targets={"greek"})
        translate.expand("克鲁塞斯", targets={"greek"})
        self.assertEqual(calls, ["克鲁塞斯"])

    def test_corpus_languages_filters_targets(self):
        got = translate.expand("特洛伊战争", targets={"latin"})
        self.assertEqual([v["lang"] for v in got], ["latin"])


class TestLlmTranslation(unittest.TestCase):
    def setUp(self):
        self.old = (config.TRANSLATE, translate._key)
        config.TRANSLATE = "llm"
        translate.clear_cache()
        translate._key = lambda: "test-key"
        self.addCleanup(self._restore)

    def _restore(self):
        config.TRANSLATE, translate._key = self.old
        translate.clear_cache()

    def test_parses_json_and_maps_language_aliases(self):
        def opener(url, data, headers, timeout):
            self.assertIn("chat/completions", url)
            return {"choices": [{"message": {"content":
                    '[{"lang":"la","text":"Achilles ira"},'
                    ' {"lang":"greek","text":"μῆνιν Ἀχιλῆος"}]'}}]}

        got = translate.llm_expand("阿喀琉斯的愤怒",
                                   {"latin", "greek"}, opener=opener)
        self.assertEqual({v["lang"] for v in got}, {"latin", "greek"})
        self.assertTrue(all(v["source"] == "llm" for v in got))

    def test_bad_json_returns_nothing(self):
        def opener(url, data, headers, timeout):
            return {"choices": [{"message": {"content": "not json"}}]}

        self.assertEqual(translate.llm_expand("x", {"latin"}, opener=opener), [])

    def test_http_failure_returns_nothing(self):
        def opener(url, data, headers, timeout):
            raise OSError("network down")

        self.assertEqual(translate.llm_expand("x", {"latin"}, opener=opener), [])

    def test_expand_merges_glossary_and_llm(self):
        old = translate.llm_expand
        translate.llm_expand = lambda q, t: [
            {"lang": "latin", "text": "Achilles ira", "source": "llm"}]
        self.addCleanup(lambda: setattr(translate, "llm_expand", old))
        got = translate.expand("阿喀琉斯的愤怒", targets={"latin"})
        sources = {v["source"] for v in got}
        self.assertIn("glossary", sources)
        self.assertIn("llm", sources)


if __name__ == "__main__":
    unittest.main()
