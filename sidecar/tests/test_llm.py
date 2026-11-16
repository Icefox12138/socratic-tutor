"""LLM route configuration and the single chat client."""
import json
import os
import sys
import unittest
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _tmp import TemporaryDirectory  # noqa: E402
from app import config, evaluations, evaluator, llm  # noqa: E402


class TestRoute(unittest.TestCase):
    def setUp(self):
        self.old = (config.LLM_BASE, config.LLM_MODEL, config.LLM_KEY_FILE)
        self.addCleanup(self._restore)

    def _restore(self):
        config.LLM_BASE, config.LLM_MODEL, config.LLM_KEY_FILE = self.old
        os.environ.pop("DEEPSEEK_API_KEY", None)

    def test_defaults_are_deepseek_but_only_as_defaults(self):
        config.LLM_BASE, config.LLM_MODEL = "https://api.deepseek.com", "deepseek-chat"
        route = llm.settings()
        self.assertEqual(route["base"], "https://api.deepseek.com")
        self.assertEqual(route["model"], "deepseek-chat")

    def test_route_comes_from_config_not_code(self):
        config.LLM_BASE, config.LLM_MODEL = "http://127.0.0.1:8000/v1", "qwen2.5:7b"
        route = llm.settings()
        self.assertEqual(route["base"], "http://127.0.0.1:8000/v1")
        self.assertEqual(route["model"], "qwen2.5:7b")
        self.assertIn("127.0.0.1:8000", route["base"])

    def test_env_key_beats_the_file(self):
        with TemporaryDirectory() as d:
            path = os.path.join(d, "key.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("from-file\n")
            config.LLM_KEY_FILE = path
            os.environ.pop("DEEPSEEK_API_KEY", None)
            self.assertEqual(llm.key(), "from-file")
            os.environ["DEEPSEEK_API_KEY"] = "from-env"
            self.assertEqual(llm.key(), "from-env")

    def test_missing_key_means_unavailable(self):
        config.LLM_KEY_FILE = os.path.join("Z:\\", "nope.txt")
        os.environ.pop("DEEPSEEK_API_KEY", None)
        if os.path.exists(os.path.join(os.getcwd(), "deepseek API key.txt")):
            self.skipTest("a key file in cwd would mask the missing-key case")
        self.assertFalse(llm.available())
        self.assertFalse(llm.provenance()["configured"])


class TestChat(unittest.TestCase):
    def setUp(self):
        self.old = (config.LLM_BASE, config.LLM_MODEL)
        config.LLM_BASE, config.LLM_MODEL = "http://local.test", "test-model"
        os.environ["DEEPSEEK_API_KEY"] = "k"
        self.addCleanup(self._restore)

    def _restore(self):
        config.LLM_BASE, config.LLM_MODEL = self.old
        os.environ.pop("DEEPSEEK_API_KEY", None)

    def test_uses_the_configured_route_and_reports_it(self):
        seen = {}

        def loader(url, payload, headers, timeout):
            seen["url"] = url
            seen["body"] = json.loads(payload)
            seen["auth"] = headers.get("Authorization")
            return {"choices": [{"message": {"content": "hi"}}], "usage": {"total_tokens": 7}}

        out = llm.chat([{"role": "user", "content": "q"}], temperature=0.2,
                       max_tokens=64, loader=loader)
        self.assertEqual(seen["url"], "http://local.test/chat/completions")
        self.assertEqual(seen["body"]["model"], "test-model")
        self.assertEqual(seen["body"]["temperature"], 0.2)
        self.assertEqual(seen["body"]["max_tokens"], 64)
        self.assertEqual(seen["auth"], "Bearer k")
        self.assertEqual(out["content"], "hi")
        self.assertEqual(out["model"], "test-model")
        self.assertEqual(out["base"], "http://local.test")
        self.assertEqual(out["usage"]["total_tokens"], 7)

    def test_http_error_is_wrapped(self):
        def loader(url, payload, headers, timeout):
            raise urllib.error.HTTPError(url, 401, "unauthorized", {}, None)

        with self.assertRaises(llm.LlmError) as ctx:
            llm.chat([{"role": "user", "content": "q"}], loader=loader)
        self.assertIn("401", str(ctx.exception))

    def test_bad_shape_is_wrapped(self):
        with self.assertRaises(llm.LlmError):
            llm.chat([{"role": "user", "content": "q"}],
                     loader=lambda *a: {"choices": []})

    def test_parse_json_tolerates_fences_and_prose(self):
        self.assertEqual(llm.parse_json('{"a": 1}'), {"a": 1})
        self.assertEqual(llm.parse_json('```json\n{"a": 2}\n```'), {"a": 2})
        self.assertEqual(llm.parse_json('sure: {"a": 3} done'), {"a": 3})
        self.assertIsNone(llm.parse_json("[1, 2]"))
        self.assertIsNone(llm.parse_json("no json here"))

    def test_chat_json_returns_data_and_meta(self):
        data, meta = llm.chat_json(
            [{"role": "user", "content": "q"}],
            loader=lambda *a: {"choices": [{"message": {"content": '{"ok": true}'}}]})
        self.assertEqual(data, {"ok": True})
        self.assertEqual(meta["model"], "test-model")


class TestEvaluatorUsesTheRoute(unittest.TestCase):
    def setUp(self):
        self.old = (config.LLM_BASE, config.LLM_MODEL, llm._http_json)
        config.LLM_BASE, config.LLM_MODEL = "http://local.test", "judge-model"
        os.environ["DEEPSEEK_API_KEY"] = "k"
        self.addCleanup(self._restore)

    def _restore(self):
        config.LLM_BASE, config.LLM_MODEL = self.old[0], self.old[1]
        llm._http_json = self.old[2]
        os.environ.pop("DEEPSEEK_API_KEY", None)

    def test_grader_goes_through_the_configured_endpoint(self):
        seen = {}

        def fake(url, payload, headers, timeout):
            seen["url"] = url
            seen["model"] = json.loads(payload)["model"]
            return {"choices": [{"message": {"content": json.dumps({
                "result": "partial", "confidence": 0.6,
                "misconceptions": ["关键点不全"], "reason": "half"})}}]}

        llm._http_json = fake
        ev = evaluator.evaluate("开放题", "只答了一半", rubric=None, use_llm=True)
        self.assertEqual(ev["result"], "partial")
        self.assertEqual(ev["source"], "llm")
        self.assertEqual(seen["url"], "http://local.test/chat/completions")
        self.assertEqual(seen["model"], "judge-model")
        self.assertEqual(ev["judge"]["model"], "judge-model")

    def test_verdict_is_persisted_with_its_judge(self):
        llm._http_json = lambda *a: {"choices": [{"message": {"content": json.dumps({
            "result": "wrong", "confidence": 0.7,
            "misconceptions": ["未命中关键点"], "reason": "no"})}}]}
        ev = evaluator.evaluate("开放题", "答错", rubric=None, use_llm=True)
        with TemporaryDirectory() as d:
            path = os.path.join(d, "state.db")
            evaluations.save("s-judge", "开放题", "答错", ev, path=path)
            rows = evaluations.list_for("s-judge", path=path)
        self.assertEqual(rows[0]["judge"] and json.loads(rows[0]["judge"])["model"],
                         "judge-model")


if __name__ == "__main__":
    unittest.main()
