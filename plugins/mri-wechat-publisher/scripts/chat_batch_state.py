#!/usr/bin/env python3
"""Count completed work and bind rolling automation chats in workflow.db."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from workflow_state_db import (
    ACTIVE_STATUSES, connect, get_metadata, immediate_transaction, now_iso, set_metadata,
)

LANES = {"writing": ("mri-09-30", 5), "recommendation": ("mri", 10)}


def completed_ids(connection: sqlite3.Connection, lane: str) -> set[str]:
    if lane == "recommendation":
        return {row[0] for row in connection.execute("SELECT cycle_id FROM recommendation_rounds")}
    # Count a paper once, including a separately prepared article, never its revisions.
    return {
        str(row[0]) for row in connection.execute(
            """SELECT CASE WHEN source_paper_id IS NULL THEN 'cycle:' || cycle_id
                      ELSE 'paper:' || source_paper_id END
               FROM articles WHERE qa_status='QA_PASSED'
               UNION
               SELECT 'paper:' || paper_id FROM prepared_drafts WHERE qa_status='QA_PASSED'"""
        )
    }


def describe(connection: sqlite3.Connection, lane: str, state: dict) -> dict:
    current = connection.execute(
        "SELECT cycle_id, status, article_json_path, preview_path FROM cycles "
        f"WHERE status IN ({','.join('?' for _ in ACTIVE_STATUSES)}) "
        "ORDER BY created_at DESC LIMIT 1", tuple(sorted(ACTIVE_STATUSES)),
    ).fetchone()
    blockers = {"AWAITING_SELECTION"} if lane == "recommendation" else {
        "WRITING", "QA_PASSED", "AWAITING_DRAFT_APPROVAL",
    }
    blocker = dict(current) if current and current["status"] in blockers else None
    count = len(state["completed_ids"]) - state["batch_start_count"]
    return {
        "lane": lane, "automation_id": state["automation_id"],
        "batch_number": state["batch_number"], "thread_id": state["thread_id"],
        "model": "gpt-6.1-sol", "reasoning_effort": "high",
        "batch_limit": state["batch_limit"], "batch_completed": count,
        "total_completed_since_setup": len(state["completed_ids"]),
        "rotation_due": count >= state["batch_limit"],
        "rotation_blocker": blocker,
        "rotation_ready": count >= state["batch_limit"] and not blocker,
        "current_cycle": dict(current) if current else None,
        "started_at": state["started_at"],
        "task_path": str(Path(__file__).resolve().parents[1] / "docs" / f"scheduled-{lane}-task.md"),
        "policy_path": str(Path(__file__).resolve().parents[1] / "docs" / "automation-chat-batches.md"),
    }


def run(connection: sqlite3.Connection, command: str, lane: str,
        thread_id: str | None = None, from_thread: str | None = None) -> dict:
    key = f"chat_batch:{lane}"
    with immediate_transaction(connection):
        state = get_metadata(connection, key)
        if command == "init":
            if state:
                if state["thread_id"] != thread_id:
                    raise ValueError("Lane is already initialized; use rotate instead of resetting counters.")
            else:
                automation_id, limit = LANES[lane]
                state = {
                    "automation_id": automation_id, "batch_limit": limit,
                    "thread_id": thread_id, "batch_number": 1,
                    "baseline_ids": sorted(completed_ids(connection, lane)),
                    "completed_ids": [], "batch_start_count": 0,
                    "started_at": now_iso(), "history": [],
                }
        if not state:
            raise ValueError("Lane is not initialized.")
        previous = set(state["completed_ids"])
        previous.update(completed_ids(connection, lane) - set(state["baseline_ids"]))
        state["completed_ids"] = sorted(previous)
        if command == "rotate":
            # A retry of the same successful handoff is a no-op.
            last = state["history"][-1] if state["history"] else None
            already_rotated = state["thread_id"] == thread_id and last and last["thread_id"] == from_thread
            if not already_rotated:
                if state["thread_id"] != from_thread:
                    raise ValueError("Stale source chat; no binding changed.")
                if not thread_id or thread_id == from_thread:
                    raise ValueError("Rotation requires a different destination chat.")
                status = describe(connection, lane, state)
                if not status["rotation_ready"]:
                    raise ValueError("Rotation is not ready; finish the batch and pending selection/draft first.")
                state["history"].append({
                    "batch_number": state["batch_number"], "thread_id": from_thread,
                    "completed": status["batch_completed"], "closed_at": now_iso(),
                })
                state["batch_number"] += 1
                state["batch_start_count"] = len(state["completed_ids"])
                state["thread_id"] = thread_id
        set_metadata(connection, key, state)
        return describe(connection, lane, state)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("command", choices=["init", "sync", "rotate"])
    parser.add_argument("--lane", required=True, choices=LANES)
    parser.add_argument("--thread-id")
    parser.add_argument("--from-thread")
    args = parser.parse_args()
    if args.command in {"init", "rotate"} and not args.thread_id:
        parser.error("--thread-id is required for init and rotate")
    if args.command == "rotate" and not args.from_thread:
        parser.error("--from-thread is required for rotate")
    if not args.db.is_file():
        parser.error("The existing workflow.db is required; this command never creates a new workflow.")
    with connect(args.db.resolve()) as connection:
        try:
            result = run(connection, args.command, args.lane, args.thread_id, args.from_thread)
        except (ValueError, sqlite3.Error) as exc:
            print(json.dumps({"status": "CHAT_BATCH_BLOCKED", "error": str(exc)}, ensure_ascii=False))
            return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
