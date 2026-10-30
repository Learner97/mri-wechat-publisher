"""Focused tests for counters, pending approvals, and idempotent chat rotation."""

import sqlite3
import unittest

from chat_batch_state import run


class ChatBatchTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:", isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE metadata(key TEXT PRIMARY KEY, value_json TEXT, updated_at TEXT);
            CREATE TABLE recommendation_rounds(cycle_id TEXT PRIMARY KEY);
            CREATE TABLE articles(cycle_id TEXT, source_paper_id INTEGER, qa_status TEXT);
            CREATE TABLE prepared_drafts(paper_id INTEGER, qa_status TEXT);
            CREATE TABLE cycles(cycle_id TEXT, status TEXT, article_json_path TEXT,
                                preview_path TEXT, created_at TEXT);
        """)

    def tearDown(self):
        self.db.close()

    def add_articles(self, count):
        self.db.executemany("INSERT INTO articles VALUES (?, ?, 'QA_PASSED')",
                            [(f"cycle-{i}", i) for i in range(count)])

    def test_history_excluded_and_repeated_sync_idempotent(self):
        self.add_articles(2)
        run(self.db, "init", "writing", "old")
        self.db.execute("INSERT INTO articles VALUES ('new', 99, 'QA_PASSED')")
        self.assertEqual(run(self.db, "sync", "writing")["batch_completed"], 1)
        self.assertEqual(run(self.db, "sync", "writing")["batch_completed"], 1)
        with self.assertRaises(ValueError):
            run(self.db, "init", "writing", "reset")

    def test_same_paper_revisions_and_prepared_duplicates_count_once(self):
        run(self.db, "init", "writing", "old")
        self.db.executemany("INSERT INTO articles VALUES (?, 9, 'QA_PASSED')", [("a",), ("b",)])
        self.db.execute("INSERT INTO prepared_drafts VALUES (9, 'QA_PASSED')")
        self.db.execute("INSERT INTO articles VALUES ('failed', 10, 'QA_FAILED')")
        self.assertEqual(run(self.db, "sync", "writing")["batch_completed"], 1)

    def test_fifth_article_waits_for_draft_then_rotates_once(self):
        run(self.db, "init", "writing", "old")
        self.add_articles(5)
        self.db.execute("INSERT INTO cycles VALUES ('fifth', 'AWAITING_DRAFT_APPROVAL', 'a', 'p', 'now')")
        status = run(self.db, "sync", "writing")
        self.assertTrue(status["rotation_due"])
        self.assertFalse(status["rotation_ready"])
        with self.assertRaises(ValueError):
            run(self.db, "rotate", "writing", "new", "old")
        self.db.execute("UPDATE cycles SET status='DRAFT_SAVED'")
        status = run(self.db, "rotate", "writing", "new", "old")
        self.assertEqual((status["batch_number"], status["batch_completed"]), (2, 0))
        self.assertEqual(run(self.db, "rotate", "writing", "new", "old")["batch_number"], 2)
        with self.assertRaises(ValueError):
            run(self.db, "rotate", "writing", "another", "old")

    def test_recommendation_tenth_round_waits_for_selection(self):
        run(self.db, "init", "recommendation", "search-old")
        self.db.executemany("INSERT INTO recommendation_rounds VALUES (?)", [(str(i),) for i in range(10)])
        self.db.execute("INSERT INTO cycles VALUES ('tenth', 'AWAITING_SELECTION', NULL, NULL, 'now')")
        self.assertFalse(run(self.db, "sync", "recommendation")["rotation_ready"])
        self.db.execute("UPDATE cycles SET status='SELECTED'")
        self.assertTrue(run(self.db, "sync", "recommendation")["rotation_ready"])

    def test_lanes_are_independent_and_early_rotation_blocked(self):
        run(self.db, "init", "writing", "write")
        run(self.db, "init", "recommendation", "search")
        self.add_articles(4)
        self.assertEqual(run(self.db, "sync", "recommendation")["batch_completed"], 0)
        with self.assertRaises(ValueError):
            run(self.db, "rotate", "writing", "new", "write")


if __name__ == "__main__":
    unittest.main()
