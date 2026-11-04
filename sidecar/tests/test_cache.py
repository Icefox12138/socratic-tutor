import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import search  # noqa: E402


class TestCache(unittest.TestCase):
    def setUp(self):
        search.clear_cache()

    def test_put_get_hit(self):
        search._cache_put(("q",), {"results": [1]})
        self.assertEqual(search._cache_get(("q",)), {"results": [1]})
        self.assertEqual(search.cache_stats()["hits"], 1)

    def test_miss(self):
        self.assertIsNone(search._cache_get(("nope",)))
        self.assertEqual(search.cache_stats()["misses"], 1)

    def test_capacity_lru(self):
        old = search.config.CACHE_SIZE
        search.config.CACHE_SIZE = 2
        try:
            search._cache_put(("a",), {"results": []})
            search._cache_put(("b",), {"results": []})
            search._cache_put(("c",), {"results": []})
            self.assertIsNone(search._cache_get(("a",)))
            self.assertIsNotNone(search._cache_get(("b",)))
        finally:
            search.config.CACHE_SIZE = old

    def test_ttl(self):
        old = search.config.CACHE_TTL
        search.config.CACHE_TTL = 0.01
        try:
            search._cache_put(("t",), {"results": []})
            time.sleep(0.03)
            self.assertIsNone(search._cache_get(("t",)))
        finally:
            search.config.CACHE_TTL = old


if __name__ == "__main__":
    unittest.main()
