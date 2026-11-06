"""Citation rows carry the policy metadata the turn card renders (tier, anchor role)."""
import os
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _tmp import TemporaryDirectory  # noqa: E402

from app import citations  # noqa: E402

RESULT = {
    "chunk_id": 7, "source": "library", "book": "数学\\x.pdf", "page": 12,
    "lang": "zh", "text": "正文片段",
    "citation": {
        "locator": "数学\\x.pdf p.12",
        "page_image": "/v1/pages?source=library&book=x&page=12",
        "tier": "B", "tier_estimated": True, "role": "cite",
        "role_in_answer": "anchor", "policy_version": "bb263d1e4d64",
    },
}

OLD_DDL = (
    "CREATE TABLE citations (id INTEGER PRIMARY KEY AUTOINCREMENT,"
    " session_id TEXT NOT NULL, turn INTEGER, step INTEGER, call_id TEXT,"
    " chunk_id INTEGER, source TEXT, book TEXT, page INTEGER, lang TEXT,"
    " document_id TEXT, scheme TEXT, url TEXT, locator TEXT, page_image TEXT,"
    " snippet TEXT, created_at REAL NOT NULL)"
)


class TestCitationStore(unittest.TestCase):
    def test_round_trip_of_policy_metadata(self):
        with TemporaryDirectory() as d:
            path = os.path.join(d, "state.db")
            self.assertEqual(
                citations.add_many("s1", [RESULT], turn=3, path=path), 1)
            rows = citations.list_for("s1", path=path)
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["tier"], "B")
            self.assertEqual(row["tier_estimated"], 1)
            self.assertEqual(row["role"], "cite")
            self.assertEqual(row["role_in_answer"], "anchor")
            self.assertEqual(row["policy_version"], "bb263d1e4d64")
            self.assertEqual(row["turn"], 3)
            self.assertEqual(row["locator"], "数学\\x.pdf p.12")

    def test_missing_metadata_is_null_not_guessed(self):
        result = {"chunk_id": 1, "source": "library", "book": "b.pdf",
                  "page": 1, "lang": "zh", "text": "t",
                  "citation": {"locator": "b.pdf p.1"}}
        with TemporaryDirectory() as d:
            path = os.path.join(d, "state.db")
            citations.add_many("s2", [result], path=path)
            row = citations.list_for("s2", path=path)[0]
            self.assertIsNone(row["tier"])
            self.assertIsNone(row["tier_estimated"])
            self.assertIsNone(row["role_in_answer"])
            self.assertIsNone(row["policy_version"])

    def test_false_estimated_is_stored_as_zero(self):
        result = dict(RESULT)
        result["citation"] = dict(RESULT["citation"], tier_estimated=False)
        with TemporaryDirectory() as d:
            path = os.path.join(d, "state.db")
            citations.add_many("s3", [result], path=path)
            row = citations.list_for("s3", path=path)[0]
            self.assertEqual(row["tier_estimated"], 0)

    def test_an_old_table_is_migrated_in_place(self):
        with TemporaryDirectory() as d:
            path = os.path.join(d, "state.db")
            con = sqlite3.connect(path)
            con.execute(OLD_DDL)
            con.execute(
                "INSERT INTO citations(session_id,turn,chunk_id,source,book,page,"
                "lang,locator,created_at) VALUES('old',1,11,'library','old.pdf',5,"
                "'zh','old.pdf p.5',1.0)")
            con.commit()
            con.close()

            citations.add_many("new", [RESULT], path=path)

            con = sqlite3.connect(path)
            cols = {r[1] for r in con.execute("PRAGMA table_info(citations)")}
            con.close()
            for name in ("tier", "tier_estimated", "role", "role_in_answer",
                         "policy_version"):
                self.assertIn(name, cols)

            old_rows = citations.list_for("old", path=path)
            self.assertEqual(old_rows[0]["locator"], "old.pdf p.5")
            self.assertIsNone(old_rows[0]["tier"])     # historical rows stay blank
            new_rows = citations.list_for("new", path=path)
            self.assertEqual(new_rows[0]["role_in_answer"], "anchor")

    def test_turn_filter_still_works(self):
        with TemporaryDirectory() as d:
            path = os.path.join(d, "state.db")
            citations.add_many("s4", [RESULT], turn=1, path=path)
            citations.add_many("s4", [RESULT], turn=2, path=path)
            self.assertEqual(len(citations.list_for("s4", path=path)), 2)
            only = citations.list_for("s4", turn=1, path=path)
            self.assertEqual([r["turn"] for r in only], [1])


if __name__ == "__main__":
    unittest.main()
