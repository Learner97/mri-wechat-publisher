#!/usr/bin/env python3
"""End-to-end tests for the SQLite workflow state layer."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

import workflow_state_db as store


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class WorkflowStateDatabaseTest(unittest.TestCase):
    def test_migration_and_full_cycle(self) -> None:
        configured_parent = os.environ.get("MRI_WECHAT_TEST_DIR", "").strip()
        if configured_parent:
            parent = Path(configured_parent).expanduser().resolve()
            parent.mkdir(parents=True, exist_ok=True)
            root = parent / f"workflow-{uuid.uuid4().hex}"
            root.mkdir(parents=True, exist_ok=False)
        else:
            root = Path(tempfile.mkdtemp(prefix="mri-wechat-workflow-test-"))
        self.addCleanup(shutil.rmtree, root, True)
        connection = None
        try:
            db_path = root / "workflow.db"
            state_path = root / "automation-workflow-state.json"
            registry_path = root / "publication-registry.json"
            legacy_cycle = "legacy-cycle"
            state = {
                "schema_version": 1,
                "workflow_id": "test-workflow",
                "timezone": "Asia/Shanghai",
                "cadence_days": 2,
                "schedule": {"recommendation_time": "17:00", "preparation_time": "09:30"},
                "current_cycle": {"cycle_id": None, "status": "IDLE"},
                "history": [
                    {
                        "cycle_id": legacy_cycle,
                        "doi": "10.1000/legacy",
                        "title": "Legacy paper",
                        "article_title": "历史文章",
                        "status": "PUBLISHED",
                        "published_at": "2026-08-01T10:00:00+08:00",
                    }
                ],
                "safety_policy": {"allow_publish": False},
                "updated_at": "2026-08-01T10:00:00+08:00",
            }
            registry = {
                "schema_version": 1,
                "statistics_mode": "manual_backend_export",
                "statistics_api_probe": {"getarticlesummary": {"available": False}},
                "articles": [
                    {
                        "publication_id": "wechat-legacy",
                        "cycle_id": legacy_cycle,
                        "doi": "10.1000/legacy",
                        "source_title": "Legacy paper",
                        "article_title": "历史文章",
                        "public_url": "https://mp.weixin.qq.com/s/legacy",
                        "published_at": "2026-08-01T10:00:00+08:00",
                        "verification": {
                            "status": "PUBLIC_PAGE_VERIFIED",
                            "http_status": 200,
                            "title_matched": True,
                            "publish_time_matched": True,
                            "verified_at": "2026-08-01T11:00:00+08:00",
                        },
                        "metric_snapshots": [
                            {
                                "label": "T+3",
                                "due_at": "2026-08-04T10:00:00+08:00",
                                "status": "WAITING_FOR_BACKEND_EXPORT",
                                "source": "wechat_backend_export",
                            }
                        ],
                    }
                ],
            }
            write_json(state_path, state)
            write_json(registry_path, registry)

            connection = store.connect(db_path)
            store.initialize(connection)
            migrated = store.migrate_legacy(connection, state_path, registry_path)
            self.assertEqual(migrated["cycles"], 1)
            self.assertEqual(migrated["publications"], 1)
            self.assertEqual(store.check_database(connection)["status"], "OK")

            recommendations_path = root / "recommendations.json"
            write_json(
                recommendations_path,
                {
                    "generated_at": "2026-08-04T17:00:00+08:00",
                    "candidates": [
                        {
                            "choice": 1,
                            "score": 95,
                            "title": "New MRI paper",
                            "journal": "Nature Neuroscience",
                            "publication_date": "2026-07-01",
                            "doi": "10.1000/new",
                            "pmid": "12345",
                            "topic_tags": ["MRI"],
                            "pilot_reason": "test",
                        },
                        {
                            "choice": 2,
                            "score": 90,
                            "title": "Second MRI paper",
                            "journal": "NeuroImage",
                            "publication_date": "2026-06-01",
                            "doi": "10.1000/second",
                        },
                        {
                            "choice": 3,
                            "score": 88,
                            "title": "Unselected MRI paper",
                            "journal": "Human Brain Mapping",
                            "publication_date": "2026-05-01",
                            "doi": "10.1000/unselected",
                        },
                    ],
                },
            )
            count = store.create_cycle(
                connection, "cycle-2026-08-04", recommendations_path, None
            )
            self.assertEqual(count, 3)
            selected = store.select_ordered_candidates(connection, [1, 2], None)
            self.assertEqual(selected["status"], "SELECTED")
            self.assertEqual(selected["selection_order"], [1, 2])
            self.assertEqual(selected["queue"][1]["status"], "QUEUED")

            first_claim = store.claim_writing(connection, "mri-09-30", "run-1")
            self.assertTrue(first_claim["claimed"])
            duplicate_claim = store.claim_writing(connection, "mri-09-30", "run-1")
            self.assertFalse(duplicate_claim["claimed"])
            self.assertEqual(duplicate_claim["reason"], "duplicate_run_key")
            competing_claim = store.claim_writing(connection, "mri-09-30", "run-2")
            self.assertFalse(competing_claim["claimed"])
            self.assertEqual(competing_claim["status"], "WRITING")

            article_path = root / "article.json"
            preview_path = root / "preview.html"
            write_json(
                article_path,
                {
                    "schema_version": 1,
                    "article_id": "article-new",
                    "publication_mode": "draft_only",
                    "title": "新文章",
                    "source": {"title": "New MRI paper", "source_id": "10.1000/new"},
                    "sections": [],
                    "figures": [],
                    "references": [],
                    "evidence_map": [],
                },
            )
            preview_path.write_text("<p>preview</p>", encoding="utf-8")
            artifact_result = store.set_artifacts(
                connection,
                "cycle-2026-08-04",
                str(article_path),
                str(preview_path),
                "QA_PASSED",
            )
            self.assertEqual(artifact_result["status"], "AWAITING_DRAFT_APPROVAL")
            store.approve_draft(connection, "cycle-2026-08-04")

            receipt_path = root / "draft-receipt.json"
            write_json(
                receipt_path,
                {
                    "status": "DRAFT_SAVED",
                    "publication_mode": "draft_only",
                    "article_id": "article-new",
                    "title": "新文章",
                    "draft_media_id": "media-new",
                    "transport": "test",
                    "saved_at_utc": "2026-08-05T02:00:00+00:00",
                    "verification": {"status": "DRAFT_GET_PASSED"},
                },
            )
            draft_result = store.record_draft(
                connection, "cycle-2026-08-04", receipt_path
            )
            self.assertEqual(draft_result["status"], "DRAFT_SAVED")
            self.assertIsNotNone(draft_result["next_queued"])
            queued_cycle_id = draft_result["next_queued"]["cycle_id"]
            self.assertEqual(draft_result["next_queued"]["choice"], 2)
            self.assertEqual(
                store.check_database(connection)["current_cycle"]["selected_doi"],
                "10.1000/second",
            )
            early_queue_claim = store.claim_writing(
                connection, "mri-09-30", "run-queue-early"
            )
            self.assertFalse(early_queue_claim["claimed"])
            self.assertEqual(early_queue_claim["reason"], "queued_not_ready")
            self.assertEqual(
                early_queue_claim["available_at"],
                draft_result["next_queued"]["available_at"],
            )

            publication_result = store.record_publication(
                connection,
                {
                    "publication_id": "wechat-new",
                    "cycle_id": "cycle-2026-08-04",
                    "doi": "10.1000/new",
                    "source_title": "New MRI paper",
                    "article_title": "新文章",
                    "public_url": "https://mp.weixin.qq.com/s/new",
                    "published_at": "2026-08-05T14:30:00+08:00",
                    "verification": {"status": "PUBLIC_PAGE_VERIFIED"},
                    "metric_snapshots": [
                        {
                            "label": "T+3",
                            "due_at": "2026-08-08T14:30:00+08:00",
                            "status": "WAITING_FOR_BACKEND_EXPORT",
                            "source": "wechat_backend_export",
                        }
                    ],
                },
            )
            self.assertEqual(publication_result["status"], "PUBLISHED")

            stats_result = store.record_stats(
                connection,
                "wechat-new",
                "2026-08-08T15:00:00+08:00",
                {"reads": 100, "shares": 8, "likes": 6, "wows": 3},
                "weekly-export.xlsx",
            )
            self.assertEqual(stats_result["publication_id"], "wechat-new")
            store.finish_job(
                connection, first_claim["job_run_id"], "SUCCEEDED", "test complete"
            )

            queued_claim = store.claim_writing(
                connection,
                "mri-09-30",
                "run-2",
                "2026-08-10T09:30:00+08:00",
            )
            self.assertTrue(queued_claim["claimed"])
            self.assertEqual(queued_claim["cycle"]["selected_doi"], "10.1000/second")
            next_after_cancel = store.transition_cycle(
                connection,
                queued_cycle_id,
                "WRITING",
                "CANCELLED",
                "test queue cancellation",
            )
            self.assertIsNone(next_after_cancel)
            store.finish_job(
                connection, queued_claim["job_run_id"], "SKIPPED", "test cancellation"
            )

            queue_state = store.selection_queue_status(connection)
            self.assertEqual(queue_state["active_count"], 0)
            self.assertEqual(queue_state["queued_count"], 0)
            self.assertEqual(
                [item["status"] for item in queue_state["items"]],
                ["COMPLETED", "CANCELLED"],
            )

            cooldown_duplicate_path = root / "cooldown-duplicate.json"
            write_json(
                cooldown_duplicate_path,
                {
                    "candidates": [
                        {
                            "choice": 1,
                            "title": "Unselected MRI paper",
                            "doi": "10.1000/unselected",
                        }
                    ]
                },
            )
            with self.assertRaisesRegex(ValueError, "5 轮冷却期"):
                store.create_cycle(
                    connection, "cooldown-duplicate", cooldown_duplicate_path, None
                )

            for round_number in range(2, 7):
                round_path = root / f"round-{round_number}.json"
                write_json(
                    round_path,
                    {
                        "candidates": [
                            {
                                "choice": 1,
                                "title": f"Fresh paper {round_number}",
                                "doi": f"10.1000/fresh-{round_number}",
                            }
                        ]
                    },
                )
                cycle_id = f"round-{round_number}"
                store.create_cycle(connection, cycle_id, round_path, None)
                store.transition_cycle(
                    connection,
                    cycle_id,
                    "AWAITING_SELECTION",
                    "CANCELLED",
                    "advance cooldown test",
                )

            eligible_count = store.create_cycle(
                connection, "round-7-reappears", cooldown_duplicate_path, None
            )
            self.assertEqual(eligible_count, 1)
            store.transition_cycle(
                connection,
                "round-7-reappears",
                "AWAITING_SELECTION",
                "CANCELLED",
                "cooldown elapsed",
            )

            permanent_duplicate_path = root / "permanent-duplicate.json"
            write_json(
                permanent_duplicate_path,
                {
                    "candidates": [
                        {"choice": 1, "title": "New MRI paper", "doi": "10.1000/new"}
                    ]
                },
            )
            with self.assertRaisesRegex(ValueError, "已选择或已排队论文"):
                store.create_cycle(
                    connection, "permanent-duplicate", permanent_duplicate_path, None
                )

            check = store.check_database(connection)
            self.assertEqual(check["status"], "OK")
            self.assertEqual(check["current_cycle"]["status"], "IDLE")
            self.assertEqual(check["counts"]["publications"], 2)
            self.assertEqual(check["counts"]["stats_snapshots"], 1)
            self.assertEqual(check["counts"]["job_runs"], 2)
            self.assertEqual(check["recommendation_policy"]["unselected_cooldown_rounds"], 5)

            exported = store.export_compatibility(connection)
            exported_state = json.loads(Path(exported["state_json"]).read_text(encoding="utf-8"))
            exported_registry = json.loads(
                Path(exported["publication_registry"]).read_text(encoding="utf-8")
            )
            self.assertEqual(exported_state["schema_version"], 2)
            self.assertEqual(exported_state["current_cycle"]["status"], "IDLE")
            self.assertEqual(len(exported_registry["articles"]), 2)

            self.assertEqual(store.check_database(connection)["current_cycle"]["status"], "IDLE")
        finally:
            if connection is not None:
                connection.close()

    def test_secret_payload_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "禁止把凭据"):
            store.ensure_safe_payload({"AppSecret": "must-not-be-stored"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
