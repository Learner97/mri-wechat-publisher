"""Focused tests for draft-only historical revisions without queue mutations."""
import json
import sqlite3
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import workflow_state_db as store


class HistoricalRevisionTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1] / "output" / "test-temp" / f"revision-{uuid.uuid4().hex}"
        self.root.mkdir(parents=True)
        self.addCleanup(self.cleanup_files)
        self.manifest = self.root / "source-manifest.json"
        self.manifest.write_text("{}", encoding="utf-8")
        self.article_path = self.root / "article.json"
        self.html_path = self.root / "article.html"
        self.article = {"article_id": "revision-1", "title": "Approved revision",
                        "source": {"doi": "10.1234/original", "source_manifest": str(self.manifest)}}
        self.hashes = {str(self.article_path): "immutable-version"}
        self.db = sqlite3.connect(":memory:", isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.addCleanup(self.db.close)
        self.db.executescript(store.SCHEMA_SQL)
        self.db.execute("INSERT INTO papers(paper_id,canonical_key,doi,title,first_seen_at,updated_at) VALUES(1,'paper','10.1234/original','Paper','t','t')")
        for cycle, status in (("history", "DRAFT_SAVED"), ("active", "SELECTED")):
            self.db.execute("INSERT INTO cycles(cycle_id,status,selected_paper_id,created_at,updated_at) VALUES(?,?,1,'t','t')", (cycle, status))
            self.db.execute("INSERT INTO selection_queue(batch_cycle_id,source_choice,paper_id,queue_position,status,processing_cycle_id,queued_at) VALUES(?,1,1,1,?,?,'t')", (cycle, "COMPLETED" if cycle == "history" else "ACTIVE", cycle))
        self.db.execute("INSERT INTO source_gates(cycle_id,paper_id,access_status,gate_status,access_check_json,input_dir,source_dir,manifest_path,created_at,updated_at) VALUES('history',1,'USER_UPLOAD_REQUIRED','SOURCE_VALIDATED','{}','input','source',?,'t','t')", (str(self.manifest),))
        self.db.execute("INSERT INTO articles(article_id,cycle_id,title,created_at,updated_at) VALUES('original','history','Old title','t','t')")
        self.db.execute("INSERT INTO drafts(cycle_id,article_id,draft_media_id,status,receipt_path,created_at) VALUES('history','original','old-media','DRAFT_SAVED','old-receipt.json','t')")
        self.before = self.protected_state()
        self.artifacts_mock = patch.object(store, "revision_artifacts", return_value=(self.article, self.hashes)).start()
        patch.object(store, "export_compatibility").start()
        self.addCleanup(patch.stopall)

    def cleanup_files(self):
        for name in ("source-manifest.json", "receipt.json", "draft-approval.json"):
            (self.root / name).unlink(missing_ok=True)
        self.root.rmdir()

    def protected_state(self):
        return {table: [dict(row) for row in self.db.execute(f"SELECT * FROM {table}")]
                for table in ("cycles", "selection_queue", "articles")}

    def approve(self):
        return store.approve_revision_draft(self.db, "history", self.article_path, self.html_path)

    def receipt(self, **changes):
        payload = {"status": "DRAFT_SAVED", "publication_mode": "draft_only",
                   "article_id": "revision-1", "title": "Approved revision", "draft_media_id": "new-media",
                   "transport": "wechat_draft_api", "saved_at_utc": "2026-08-31T04:00:00Z",
                   "verification": {"status": "DRAFT_GET_PASSED", "title_matched": True}}
        payload.update(changes)
        path = self.root / "receipt.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_save_revision_preserves_cycles_queue_and_original(self):
        with self.assertRaises(ValueError):
            store.approve_draft(self.db, "history")
        self.assertEqual(self.approve()["status"], "REVISION_APPROVED")
        receipt = self.receipt()
        result = store.record_draft(self.db, "history", receipt)
        self.assertFalse(result["queue_changed"])
        self.assertEqual(store.record_draft(self.db, "history", receipt)["status"], "DRAFT_SAVED")
        self.assertEqual(self.protected_state(), self.before)
        rows = self.db.execute("SELECT * FROM drafts ORDER BY draft_id").fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["receipt_path"], "old-receipt.json")
        self.assertIsNone(rows[1]["article_id"])
        self.assertEqual(rows[1]["draft_media_id"], "new-media")
        self.assertEqual(self.db.execute("PRAGMA foreign_key_check").fetchall(), [])
        with self.assertRaises(ValueError):
            self.approve()
        with self.assertRaises(ValueError):
            store.record_draft(self.db, "history", self.receipt(draft_media_id="duplicate-media"))

    def test_requires_approval_and_verified_matching_receipt(self):
        with self.assertRaises(ValueError):
            store.record_draft(self.db, "history", self.receipt())
        self.approve()
        for changes in ({"verification": {}}, {"title": "Wrong title"}, {"publication_mode": "publish"}):
            with self.assertRaises(ValueError):
                store.record_draft(self.db, "history", self.receipt(**changes))
        with self.assertRaises(ValueError):
            store.record_draft(self.db, "active", self.receipt())
        self.assertEqual(self.protected_state(), self.before)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM drafts").fetchone()[0], 1)

    def test_rejects_changed_artifacts_and_wrong_source_or_cycle(self):
        with self.assertRaises(ValueError):
            store.approve_revision_draft(self.db, "active", self.article_path, self.html_path)
        self.article["source"]["doi"] = "10.1234/wrong"
        with self.assertRaises(ValueError):
            self.approve()
        self.article["source"]["doi"] = "10.1234/original"
        self.approve()
        self.artifacts_mock.return_value = (self.article, {str(self.article_path): "changed"})
        with self.assertRaises(ValueError):
            store.record_draft(self.db, "history", self.receipt())
        with self.assertRaises(ValueError):
            self.approve()
        self.assertEqual(self.protected_state(), self.before)


if __name__ == "__main__":
    unittest.main()
