#!/usr/bin/env python3
"""Transactional workflow state for the MRI WeChat publisher.

The database never stores WeChat credentials. JSON files remain compatibility
snapshots so a human can inspect state and older tooling can be rolled back.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PLUGIN_ROOT / "output" / "workflow.db"
DEFAULT_STATE_JSON = PLUGIN_ROOT / "output" / "automation-workflow-state.json"
DEFAULT_PUBLICATION_JSON = PLUGIN_ROOT / "output" / "publication-registry.json"
DEFAULT_COOLDOWN_ROUNDS = 5

ACTIVE_STATUSES = {
    "AWAITING_SELECTION",
    "SELECTED",
    "WRITING",
    "QA_PASSED",
    "AWAITING_DRAFT_APPROVAL",
    "EVIDENCE_BLOCKED",
}
TERMINAL_STATUSES = {"DRAFT_SAVED", "PUBLISHED", "COMPLETED", "CANCELLED"}
ALL_STATUSES = ACTIVE_STATUSES | TERMINAL_STATUSES
ALLOWED_TRANSITIONS = {
    "AWAITING_SELECTION": {"SELECTED", "CANCELLED"},
    "SELECTED": {"WRITING", "EVIDENCE_BLOCKED", "CANCELLED"},
    "WRITING": {"AWAITING_DRAFT_APPROVAL", "EVIDENCE_BLOCKED", "CANCELLED"},
    "QA_PASSED": {"AWAITING_DRAFT_APPROVAL", "CANCELLED"},
    "EVIDENCE_BLOCKED": {"SELECTED", "WRITING", "CANCELLED"},
    "AWAITING_DRAFT_APPROVAL": {"DRAFT_SAVED", "CANCELLED"},
    "DRAFT_SAVED": {"PUBLISHED", "COMPLETED"},
    "COMPLETED": {"PUBLISHED"},
    "PUBLISHED": set(),
    "CANCELLED": set(),
}
FORBIDDEN_KEYS = {
    "wechat_app_secret",
    "appsecret",
    "app_secret",
    "access_token",
    "cookie",
    "cookies",
    "session_cookie",
}


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS papers (
    paper_id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_key TEXT NOT NULL UNIQUE,
    doi TEXT UNIQUE COLLATE NOCASE,
    pmid TEXT UNIQUE,
    pmcid TEXT,
    title TEXT NOT NULL,
    journal TEXT,
    publication_date TEXT,
    first_seen_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cycles (
    cycle_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    candidate_pool_path TEXT,
    recommended_at TEXT,
    selected_choice INTEGER,
    selected_paper_id INTEGER REFERENCES papers(paper_id),
    selected_at TEXT,
    article_json_path TEXT,
    preview_path TEXT,
    qa_status TEXT,
    user_draft_approval INTEGER NOT NULL DEFAULT 0 CHECK (user_draft_approval IN (0, 1)),
    draft_receipt_path TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    CHECK (status IN (
        'AWAITING_SELECTION','SELECTED','WRITING','QA_PASSED',
        'AWAITING_DRAFT_APPROVAL','EVIDENCE_BLOCKED','DRAFT_SAVED',
        'PUBLISHED','COMPLETED','CANCELLED'
    ))
);

CREATE UNIQUE INDEX IF NOT EXISTS one_active_cycle
ON cycles((1))
WHERE status IN (
    'AWAITING_SELECTION','SELECTED','WRITING','QA_PASSED',
    'AWAITING_DRAFT_APPROVAL','EVIDENCE_BLOCKED'
);

CREATE TABLE IF NOT EXISTS candidates (
    cycle_id TEXT NOT NULL REFERENCES cycles(cycle_id) ON DELETE CASCADE,
    choice INTEGER NOT NULL,
    paper_id INTEGER NOT NULL REFERENCES papers(paper_id),
    score REAL,
    topic_tags_json TEXT NOT NULL DEFAULT '[]',
    recommendation_reason TEXT,
    source_json TEXT NOT NULL,
    PRIMARY KEY (cycle_id, choice),
    UNIQUE (cycle_id, paper_id)
);

CREATE INDEX IF NOT EXISTS candidates_paper_idx ON candidates(paper_id);

CREATE TABLE IF NOT EXISTS recommendation_rounds (
    cycle_id TEXT PRIMARY KEY REFERENCES cycles(cycle_id) ON DELETE CASCADE,
    round_number INTEGER NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS selection_queue (
    queue_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_cycle_id TEXT NOT NULL REFERENCES cycles(cycle_id),
    source_choice INTEGER NOT NULL,
    paper_id INTEGER NOT NULL REFERENCES papers(paper_id),
    queue_position INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('QUEUED','ACTIVE','COMPLETED','CANCELLED')),
    processing_cycle_id TEXT UNIQUE REFERENCES cycles(cycle_id),
    queued_at TEXT NOT NULL,
    activated_at TEXT,
    available_at TEXT,
    completed_at TEXT,
    UNIQUE (batch_cycle_id, source_choice),
    UNIQUE (batch_cycle_id, queue_position)
);

CREATE INDEX IF NOT EXISTS selection_queue_status_idx
ON selection_queue(status, queue_position);

CREATE INDEX IF NOT EXISTS selection_queue_paper_idx
ON selection_queue(paper_id);

CREATE TABLE IF NOT EXISTS articles (
    article_id TEXT PRIMARY KEY,
    cycle_id TEXT NOT NULL UNIQUE REFERENCES cycles(cycle_id),
    source_paper_id INTEGER REFERENCES papers(paper_id),
    title TEXT NOT NULL,
    article_json_path TEXT,
    preview_path TEXT,
    qa_status TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS drafts (
    draft_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id TEXT NOT NULL REFERENCES cycles(cycle_id),
    article_id TEXT REFERENCES articles(article_id),
    draft_media_id TEXT UNIQUE,
    title TEXT,
    transport TEXT,
    status TEXT NOT NULL,
    receipt_path TEXT,
    saved_at TEXT,
    verification_status TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS publications (
    publication_id TEXT PRIMARY KEY,
    cycle_id TEXT REFERENCES cycles(cycle_id),
    paper_id INTEGER REFERENCES papers(paper_id),
    source_title TEXT,
    article_title TEXT NOT NULL,
    public_url TEXT NOT NULL UNIQUE,
    published_at TEXT NOT NULL,
    verification_status TEXT,
    verification_http_status INTEGER,
    title_matched INTEGER,
    publish_time_matched INTEGER,
    verified_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metric_checkpoints (
    checkpoint_id INTEGER PRIMARY KEY AUTOINCREMENT,
    publication_id TEXT NOT NULL REFERENCES publications(publication_id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    due_at TEXT NOT NULL,
    status TEXT NOT NULL,
    source TEXT NOT NULL,
    UNIQUE (publication_id, label)
);

CREATE TABLE IF NOT EXISTS stats_imports (
    import_id TEXT PRIMARY KEY,
    imported_at TEXT NOT NULL,
    source_path TEXT,
    source_kind TEXT NOT NULL,
    note TEXT
);

CREATE TABLE IF NOT EXISTS stats_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    publication_id TEXT NOT NULL REFERENCES publications(publication_id) ON DELETE CASCADE,
    import_id TEXT REFERENCES stats_imports(import_id),
    observed_at TEXT NOT NULL,
    reads INTEGER,
    readers INTEGER,
    shares INTEGER,
    sharers INTEGER,
    likes INTEGER,
    wows INTEGER,
    favorites INTEGER,
    comments INTEGER,
    delivered INTEGER,
    new_followers INTEGER,
    raw_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (publication_id, observed_at)
);

CREATE TABLE IF NOT EXISTS job_runs (
    job_run_id TEXT PRIMARY KEY,
    run_key TEXT UNIQUE,
    automation_id TEXT NOT NULL,
    job_kind TEXT NOT NULL,
    cycle_id TEXT REFERENCES cycles(cycle_id),
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    detail TEXT
);
"""


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def normalize_doi(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if text.startswith("https://doi.org/"):
        text = text.removeprefix("https://doi.org/")
    return text or None


def canonical_paper_key(candidate: dict[str, Any]) -> str:
    doi = normalize_doi(candidate.get("doi"))
    if doi:
        return f"doi:{doi}"
    pmid = str(candidate.get("pmid") or "").strip()
    if pmid:
        return f"pmid:{pmid}"
    title = " ".join(str(candidate.get("title") or "").lower().split())
    if not title:
        raise ValueError("论文至少需要 DOI、PMID 或题名之一。")
    digest = hashlib.sha256(title.encode("utf-8")).hexdigest()
    return f"title:{digest}"


def ensure_safe_payload(value: Any, location: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            child_location = f"{location}.{key}"
            if normalized in FORBIDDEN_KEYS and str(child or "").strip():
                raise ValueError(f"禁止把凭据写入工作流数据库：{child_location}")
            ensure_safe_payload(child, child_location)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            ensure_safe_payload(child, f"{location}[{index}]")


def ensure_safe_text(value: str | None, location: str) -> None:
    text = str(value or "").lower()
    markers = ("appsecret", "app_secret", "access_token", "session_cookie", "cookie=")
    if any(marker in text for marker in markers):
        raise ValueError(f"文本可能包含凭据，拒绝写入：{location}")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"JSON 根节点必须是对象：{path}")
    ensure_safe_payload(value)
    return value


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA synchronous = FULL")
    return connection


@contextmanager
def immediate_transaction(connection: sqlite3.Connection) -> Iterator[None]:
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()


def initialize(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA_SQL)
    timestamp = now_iso()
    queue_columns = {
        str(row["name"])
        for row in connection.execute("PRAGMA table_info(selection_queue)")
    }
    if "available_at" not in queue_columns:
        connection.execute("ALTER TABLE selection_queue ADD COLUMN available_at TEXT")
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(1, ?)",
        (timestamp,),
    )
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(2, ?)",
        (timestamp,),
    )
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(3, ?)",
        (timestamp,),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO metadata(key, value_json, updated_at)
        VALUES('recommendation_policy', ?, ?)
        """,
        (
            json.dumps(
                {"unselected_cooldown_rounds": DEFAULT_COOLDOWN_ROUNDS},
                ensure_ascii=False,
            ),
            timestamp,
        ),
    )
    # Backfill recommendation-round numbers for databases created before v2.
    next_round = int(
        connection.execute(
            "SELECT COALESCE(MAX(round_number), 0) FROM recommendation_rounds"
        ).fetchone()[0]
    )
    legacy_rounds = connection.execute(
        """
        SELECT c.cycle_id
        FROM cycles c
        WHERE c.candidate_pool_path IS NOT NULL
          AND NOT EXISTS(
              SELECT 1 FROM recommendation_rounds r WHERE r.cycle_id=c.cycle_id
          )
          AND NOT EXISTS(
              SELECT 1 FROM selection_queue q
              WHERE q.processing_cycle_id=c.cycle_id AND q.batch_cycle_id<>c.cycle_id
          )
        ORDER BY COALESCE(c.recommended_at, c.created_at), c.cycle_id
        """
    ).fetchall()
    for row in legacy_rounds:
        next_round += 1
        connection.execute(
            """
            INSERT INTO recommendation_rounds(cycle_id, round_number, created_at)
            VALUES(?, ?, ?)
            """,
            (row["cycle_id"], next_round, timestamp),
        )


def set_metadata(connection: sqlite3.Connection, key: str, value: Any) -> None:
    timestamp = now_iso()
    connection.execute(
        """
        INSERT INTO metadata(key, value_json, updated_at) VALUES(?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at
        """,
        (key, json.dumps(value, ensure_ascii=False), timestamp),
    )


def get_metadata(connection: sqlite3.Connection, key: str, default: Any = None) -> Any:
    row = connection.execute("SELECT value_json FROM metadata WHERE key=?", (key,)).fetchone()
    return json.loads(row["value_json"]) if row else default


def recommendation_policy(connection: sqlite3.Connection) -> dict[str, int]:
    value = get_metadata(
        connection,
        "recommendation_policy",
        {"unselected_cooldown_rounds": DEFAULT_COOLDOWN_ROUNDS},
    )
    try:
        rounds = int(value.get("unselected_cooldown_rounds", DEFAULT_COOLDOWN_ROUNDS))
    except (AttributeError, TypeError, ValueError):
        rounds = DEFAULT_COOLDOWN_ROUNDS
    if rounds < 0:
        raise ValueError("未选论文的冷却轮数不能小于 0。")
    return {"unselected_cooldown_rounds": rounds}


def next_queue_preparation_at(connection: sqlite3.Connection, activated_at: str) -> str:
    workflow = get_metadata(connection, "workflow", {})
    schedule = get_metadata(connection, "schedule", {})
    if not isinstance(workflow, dict):
        workflow = {}
    if not isinstance(schedule, dict):
        schedule = {}
    try:
        cadence_days = max(1, int(workflow.get("cadence_days", 2)))
    except (AttributeError, TypeError, ValueError):
        cadence_days = 2
    preparation_text = str(schedule.get("preparation_time") or "09:30")
    try:
        hour, minute = (int(part) for part in preparation_text.split(":", 1))
        preparation_time = time(hour=hour, minute=minute)
    except (TypeError, ValueError):
        preparation_time = time(hour=9, minute=30)
    activated = datetime.fromisoformat(activated_at)
    timezone = ZoneInfo(str(workflow.get("timezone") or "Asia/Shanghai"))
    if activated.tzinfo is None:
        activated = activated.replace(tzinfo=timezone)
    local_activated = activated.astimezone(timezone)
    target_date = local_activated.date() + timedelta(days=cadence_days)
    available = datetime.combine(target_date, preparation_time, tzinfo=timezone)
    return available.isoformat(timespec="seconds")


def next_recommendation_round(connection: sqlite3.Connection) -> int:
    return int(
        connection.execute(
            "SELECT COALESCE(MAX(round_number), 0) + 1 FROM recommendation_rounds"
        ).fetchone()[0]
    )


def permanent_selection_cycle(
    connection: sqlite3.Connection, paper_id: int
) -> str | None:
    row = connection.execute(
        """
        SELECT cycle_id
        FROM cycles
        WHERE selected_paper_id=?
        ORDER BY COALESCE(selected_at, created_at)
        LIMIT 1
        """,
        (paper_id,),
    ).fetchone()
    if row:
        return str(row["cycle_id"])
    queued = connection.execute(
        """
        SELECT batch_cycle_id
        FROM selection_queue
        WHERE paper_id=?
        ORDER BY queued_at
        LIMIT 1
        """,
        (paper_id,),
    ).fetchone()
    return str(queued["batch_cycle_id"]) if queued else None


def recent_recommendation_round(
    connection: sqlite3.Connection,
    paper_id: int,
    current_round_number: int,
    cooldown_rounds: int,
) -> int | None:
    if cooldown_rounds <= 0:
        return None
    first_blocked_round = max(1, current_round_number - cooldown_rounds)
    row = connection.execute(
        """
        SELECT MAX(r.round_number) AS round_number
        FROM candidates c
        JOIN recommendation_rounds r ON r.cycle_id=c.cycle_id
        WHERE c.paper_id=?
          AND r.round_number>=?
          AND r.round_number<?
        """,
        (paper_id, first_blocked_round, current_round_number),
    ).fetchone()
    return int(row["round_number"]) if row and row["round_number"] is not None else None


def candidate_ineligibility(
    connection: sqlite3.Connection,
    paper_id: int,
    current_round_number: int,
    cooldown_rounds: int,
) -> dict[str, Any] | None:
    selected_cycle = permanent_selection_cycle(connection, paper_id)
    if selected_cycle:
        return {
            "reason": "permanently_selected",
            "cycle_id": selected_cycle,
        }
    recent_round = recent_recommendation_round(
        connection, paper_id, current_round_number, cooldown_rounds
    )
    if recent_round is not None:
        return {
            "reason": "cooldown",
            "last_recommended_round": recent_round,
            "eligible_from_round": recent_round + cooldown_rounds + 1,
        }
    return None


def upsert_paper(connection: sqlite3.Connection, candidate: dict[str, Any]) -> int:
    ensure_safe_payload(candidate)
    timestamp = now_iso()
    key = canonical_paper_key(candidate)
    doi = normalize_doi(candidate.get("doi"))
    pmid = str(candidate.get("pmid") or "").strip() or None
    title = str(candidate.get("title") or "").strip()
    connection.execute(
        """
        INSERT INTO papers(
            canonical_key, doi, pmid, pmcid, title, journal, publication_date,
            first_seen_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(canonical_key) DO UPDATE SET
            doi=COALESCE(excluded.doi, papers.doi),
            pmid=COALESCE(excluded.pmid, papers.pmid),
            pmcid=COALESCE(excluded.pmcid, papers.pmcid),
            title=CASE WHEN excluded.title <> '' THEN excluded.title ELSE papers.title END,
            journal=COALESCE(excluded.journal, papers.journal),
            publication_date=COALESCE(excluded.publication_date, papers.publication_date),
            updated_at=excluded.updated_at
        """,
        (
            key,
            doi,
            pmid,
            str(candidate.get("pmcid") or "").strip() or None,
            title,
            str(candidate.get("journal") or "").strip() or None,
            str(candidate.get("publication_date") or "").strip() or None,
            timestamp,
            timestamp,
        ),
    )
    row = connection.execute("SELECT paper_id FROM papers WHERE canonical_key=?", (key,)).fetchone()
    assert row is not None
    return int(row["paper_id"])


def insert_candidates(
    connection: sqlite3.Connection,
    cycle_id: str,
    recommendation_payload: dict[str, Any],
    *,
    reject_previous: bool,
    recommendation_round_number: int | None = None,
    cooldown_rounds: int = DEFAULT_COOLDOWN_ROUNDS,
) -> int:
    candidates = recommendation_payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("候选文件必须包含非空 candidates 数组。")
    inserted = 0
    for index, candidate in enumerate(candidates, start=1):
        if not isinstance(candidate, dict):
            raise ValueError(f"candidates[{index - 1}] 必须是对象。")
        choice = int(candidate.get("choice") or index)
        paper_id = upsert_paper(connection, candidate)
        if reject_previous:
            if recommendation_round_number is None:
                raise ValueError("启用候选去重时必须提供推荐轮次。")
            ineligibility = candidate_ineligibility(
                connection,
                paper_id,
                recommendation_round_number,
                cooldown_rounds,
            )
            if ineligibility and ineligibility["reason"] == "permanently_selected":
                raise ValueError(
                    "检测到已选择或已排队论文："
                    f"choice={choice}，此前周期={ineligibility['cycle_id']}"
                )
            if ineligibility and ineligibility["reason"] == "cooldown":
                raise ValueError(
                    f"检测到处于 {cooldown_rounds} 轮冷却期的论文：choice={choice}，"
                    f"上次推荐轮次={ineligibility['last_recommended_round']}，"
                    f"最早可在第 {ineligibility['eligible_from_round']} 轮再次推荐"
                )
        connection.execute(
            """
            INSERT INTO candidates(
                cycle_id, choice, paper_id, score, topic_tags_json,
                recommendation_reason, source_json
            ) VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cycle_id, choice) DO UPDATE SET
                paper_id=excluded.paper_id,
                score=excluded.score,
                topic_tags_json=excluded.topic_tags_json,
                recommendation_reason=excluded.recommendation_reason,
                source_json=excluded.source_json
            """,
            (
                cycle_id,
                choice,
                paper_id,
                candidate.get("score"),
                json.dumps(candidate.get("topic_tags") or [], ensure_ascii=False),
                str(candidate.get("pilot_reason") or candidate.get("reason") or "").strip()
                or None,
                json.dumps(candidate, ensure_ascii=False),
            ),
        )
        inserted += 1
    return inserted


def active_cycle(connection: sqlite3.Connection) -> sqlite3.Row | None:
    placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
    return connection.execute(
        f"SELECT * FROM cycles WHERE status IN ({placeholders}) ORDER BY created_at DESC LIMIT 1",
        tuple(sorted(ACTIVE_STATUSES)),
    ).fetchone()


def selected_paper(connection: sqlite3.Connection, cycle: sqlite3.Row) -> sqlite3.Row | None:
    paper_id = cycle["selected_paper_id"]
    if paper_id is None:
        return None
    return connection.execute("SELECT * FROM papers WHERE paper_id=?", (paper_id,)).fetchone()


def cycle_dict(connection: sqlite3.Connection, cycle: sqlite3.Row | None) -> dict[str, Any]:
    if cycle is None:
        return {
            "cycle_id": None,
            "status": "IDLE",
            "candidate_pool_path": None,
            "recommended_at": None,
            "selected_choice": None,
            "selected_doi": None,
            "selected_at": None,
            "article_json_path": None,
            "preview_path": None,
            "qa_status": None,
            "user_draft_approval": False,
            "draft_receipt_path": None,
            "queue_position": None,
            "available_at": None,
        }
    paper = selected_paper(connection, cycle)
    queue_item = connection.execute(
        """
        SELECT queue_position, available_at
        FROM selection_queue
        WHERE processing_cycle_id=? AND status='ACTIVE'
        """,
        (cycle["cycle_id"],),
    ).fetchone()
    return {
        "cycle_id": cycle["cycle_id"],
        "status": cycle["status"],
        "candidate_pool_path": cycle["candidate_pool_path"],
        "recommended_at": cycle["recommended_at"],
        "selected_choice": cycle["selected_choice"],
        "selected_doi": paper["doi"] if paper else None,
        "selected_at": cycle["selected_at"],
        "article_json_path": cycle["article_json_path"],
        "preview_path": cycle["preview_path"],
        "qa_status": cycle["qa_status"],
        "user_draft_approval": bool(cycle["user_draft_approval"]),
        "draft_receipt_path": cycle["draft_receipt_path"],
        "queue_position": int(queue_item["queue_position"]) if queue_item else None,
        "available_at": queue_item["available_at"] if queue_item else None,
    }


def selection_queue_status(connection: sqlite3.Connection) -> dict[str, Any]:
    rows = connection.execute(
        """
        SELECT q.batch_cycle_id, q.source_choice, q.queue_position, q.status,
               q.processing_cycle_id, q.queued_at, q.activated_at, q.completed_at,
               q.available_at, p.doi, p.pmid, p.title, p.journal
        FROM selection_queue q
        JOIN papers p ON p.paper_id=q.paper_id
        ORDER BY q.queued_at, q.batch_cycle_id, q.queue_position
        """
    ).fetchall()
    items = [dict(row) for row in rows]
    return {
        "active_count": sum(item["status"] == "ACTIVE" for item in items),
        "queued_count": sum(item["status"] == "QUEUED" for item in items),
        "items": items,
    }


def recommendation_exclusions(
    connection: sqlite3.Connection, cooldown_rounds: int | None = None
) -> dict[str, Any]:
    policy_rounds = recommendation_policy(connection)["unselected_cooldown_rounds"]
    rounds = policy_rounds if cooldown_rounds is None else int(cooldown_rounds)
    if rounds < 0:
        raise ValueError("冷却轮数不能小于 0。")
    next_round = next_recommendation_round(connection)
    permanent_rows = connection.execute(
        """
        WITH permanent_papers AS (
            SELECT selected_paper_id AS paper_id, cycle_id AS source_cycle
            FROM cycles
            WHERE selected_paper_id IS NOT NULL
            UNION
            SELECT paper_id, batch_cycle_id AS source_cycle
            FROM selection_queue
        )
        SELECT p.paper_id, p.doi, p.pmid, p.title, p.journal,
               MIN(pp.source_cycle) AS source_cycle,
               'permanently_selected' AS reason
        FROM permanent_papers pp
        JOIN papers p ON p.paper_id=pp.paper_id
        GROUP BY p.paper_id, p.doi, p.pmid, p.title, p.journal
        ORDER BY p.paper_id
        """
    ).fetchall()
    permanent_ids = {int(row["paper_id"]) for row in permanent_rows}
    first_blocked_round = max(1, next_round - rounds)
    cooldown_rows = connection.execute(
        """
        SELECT p.paper_id, p.doi, p.pmid, p.title, p.journal,
               MAX(r.round_number) AS last_recommended_round
        FROM candidates c
        JOIN recommendation_rounds r ON r.cycle_id=c.cycle_id
        JOIN papers p ON p.paper_id=c.paper_id
        WHERE r.round_number>=? AND r.round_number<?
        GROUP BY p.paper_id, p.doi, p.pmid, p.title, p.journal
        ORDER BY last_recommended_round DESC, p.paper_id
        """,
        (first_blocked_round, next_round),
    ).fetchall()
    cooldown_items = []
    for row in cooldown_rows:
        if int(row["paper_id"]) in permanent_ids:
            continue
        item = dict(row)
        item["reason"] = "cooldown"
        item["eligible_from_round"] = int(item["last_recommended_round"]) + rounds + 1
        cooldown_items.append(item)
    return {
        "policy": {"unselected_cooldown_rounds": rounds},
        "next_recommendation_round": next_round,
        "permanent_exclusions": [dict(row) for row in permanent_rows],
        "cooldown_exclusions": cooldown_items,
    }


def history_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT c.*, p.doi, p.title AS source_title, a.title AS article_title,
               pub.publication_id, pub.public_url, pub.published_at
        FROM cycles c
        LEFT JOIN papers p ON p.paper_id=c.selected_paper_id
        LEFT JOIN articles a ON a.cycle_id=c.cycle_id
        LEFT JOIN publications pub ON pub.cycle_id=c.cycle_id
        WHERE c.status IN ('DRAFT_SAVED','PUBLISHED','COMPLETED','CANCELLED')
        ORDER BY c.created_at
        """
    ).fetchall()
    history: list[dict[str, Any]] = []
    for row in rows:
        history.append(
            {
                "cycle_id": row["cycle_id"],
                "doi": row["doi"],
                "title": row["source_title"],
                "article_title": row["article_title"],
                "status": row["status"],
                "draft_receipt_path": row["draft_receipt_path"],
                "public_url": row["public_url"],
                "published_at": row["published_at"],
                "metrics_registry_path": str(
                    get_metadata(connection, "publication_registry_path", DEFAULT_PUBLICATION_JSON)
                ),
            }
        )
    return history


def export_compatibility(connection: sqlite3.Connection) -> dict[str, str]:
    state_path = Path(get_metadata(connection, "state_json_path", str(DEFAULT_STATE_JSON)))
    publication_path = Path(
        get_metadata(connection, "publication_registry_path", str(DEFAULT_PUBLICATION_JSON))
    )
    workflow = get_metadata(connection, "workflow", {})
    schedule = get_metadata(connection, "schedule", {})
    safety_policy = get_metadata(connection, "safety_policy", {})
    current = cycle_dict(connection, active_cycle(connection))
    database_row = connection.execute("PRAGMA database_list").fetchone()
    database_path = str(Path(database_row["file"]).resolve()) if database_row else str(DEFAULT_DB)
    state_payload = {
        "schema_version": 2,
        "storage": {"primary": "sqlite", "database_path": database_path},
        "workflow_id": workflow.get("workflow_id", "mri-wechat-every-two-days"),
        "timezone": workflow.get("timezone", "Asia/Shanghai"),
        "cadence_days": workflow.get("cadence_days", 2),
        "schedule": schedule,
        "recommendation_policy": recommendation_policy(connection),
        "current_cycle": current,
        "selection_queue": selection_queue_status(connection),
        "history": history_rows(connection),
        "safety_policy": safety_policy,
        "updated_at": now_iso(),
    }

    publications = connection.execute(
        "SELECT * FROM publications ORDER BY published_at"
    ).fetchall()
    publication_articles: list[dict[str, Any]] = []
    for publication in publications:
        paper = None
        if publication["paper_id"] is not None:
            paper = connection.execute(
                "SELECT * FROM papers WHERE paper_id=?", (publication["paper_id"],)
            ).fetchone()
        checkpoints = connection.execute(
            """
            SELECT label, due_at, status, source FROM metric_checkpoints
            WHERE publication_id=? ORDER BY due_at
            """,
            (publication["publication_id"],),
        ).fetchall()
        publication_articles.append(
            {
                "publication_id": publication["publication_id"],
                "cycle_id": publication["cycle_id"],
                "doi": paper["doi"] if paper else None,
                "source_title": publication["source_title"],
                "article_title": publication["article_title"],
                "public_url": publication["public_url"],
                "published_at": publication["published_at"],
                "verification": {
                    "status": publication["verification_status"],
                    "http_status": publication["verification_http_status"],
                    "title_matched": bool(publication["title_matched"]),
                    "publish_time_matched": bool(publication["publish_time_matched"]),
                    "verified_at": publication["verified_at"],
                },
                "metric_snapshots": [dict(checkpoint) for checkpoint in checkpoints],
            }
        )
    publication_payload = {
        "schema_version": 2,
        "storage": {"primary": "sqlite", "database_path": database_path},
        "timezone": workflow.get("timezone", "Asia/Shanghai"),
        "statistics_mode": get_metadata(connection, "statistics_mode", "manual_backend_export"),
        "statistics_api_probe": get_metadata(connection, "statistics_api_probe", {}),
        "articles": publication_articles,
        "updated_at": now_iso(),
    }
    atomic_write_json(state_path, state_payload)
    atomic_write_json(publication_path, publication_payload)
    return {"state_json": str(state_path), "publication_registry": str(publication_path)}


def migrate_legacy(
    connection: sqlite3.Connection, state_path: Path, publication_path: Path
) -> dict[str, int]:
    state = load_json(state_path)
    registry = load_json(publication_path)
    counters = {"cycles": 0, "publications": 0, "checkpoints": 0}
    with immediate_transaction(connection):
        set_metadata(
            connection,
            "workflow",
            {
                "workflow_id": state.get("workflow_id", "mri-wechat-every-two-days"),
                "timezone": state.get("timezone", "Asia/Shanghai"),
                "cadence_days": state.get("cadence_days", 2),
            },
        )
        set_metadata(connection, "schedule", state.get("schedule") or {})
        set_metadata(connection, "safety_policy", state.get("safety_policy") or {})
        set_metadata(connection, "statistics_mode", registry.get("statistics_mode"))
        set_metadata(connection, "statistics_api_probe", registry.get("statistics_api_probe") or {})
        set_metadata(connection, "state_json_path", str(state_path.resolve()))
        set_metadata(connection, "publication_registry_path", str(publication_path.resolve()))

        for item in state.get("history") or []:
            if not isinstance(item, dict) or not item.get("cycle_id"):
                continue
            paper_id = upsert_paper(
                connection,
                {
                    "doi": item.get("doi"),
                    "title": item.get("title") or item.get("article_title") or "未知论文",
                },
            )
            timestamp = item.get("published_at") or state.get("updated_at") or now_iso()
            status = str(item.get("status") or "COMPLETED")
            if status not in ALL_STATUSES:
                status = "COMPLETED"
            connection.execute(
                """
                INSERT INTO cycles(
                    cycle_id, status, selected_paper_id, selected_at,
                    draft_receipt_path, created_at, updated_at, completed_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cycle_id) DO UPDATE SET
                    status=excluded.status,
                    selected_paper_id=excluded.selected_paper_id,
                    draft_receipt_path=excluded.draft_receipt_path,
                    updated_at=excluded.updated_at,
                    completed_at=excluded.completed_at
                """,
                (
                    item["cycle_id"],
                    status,
                    paper_id,
                    timestamp,
                    item.get("draft_receipt_path"),
                    timestamp,
                    timestamp,
                    timestamp,
                ),
            )
            counters["cycles"] += 1
            article_title = str(item.get("article_title") or "").strip()
            if article_title:
                article_id = f"migrated-{item['cycle_id']}"
                connection.execute(
                    """
                    INSERT INTO articles(
                        article_id, cycle_id, source_paper_id, title, qa_status,
                        created_at, updated_at
                    ) VALUES(?, ?, ?, ?, 'QA_PASSED', ?, ?)
                    ON CONFLICT(cycle_id) DO UPDATE SET title=excluded.title, updated_at=excluded.updated_at
                    """,
                    (article_id, item["cycle_id"], paper_id, article_title, timestamp, timestamp),
                )
            receipt_path = item.get("draft_receipt_path")
            if receipt_path:
                resolved_receipt = (PLUGIN_ROOT.parents[1] / receipt_path).resolve()
                if resolved_receipt.is_file():
                    receipt = load_json(resolved_receipt)
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO drafts(
                            cycle_id, article_id, draft_media_id, title, transport, status,
                            receipt_path, saved_at, verification_status, created_at
                        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item["cycle_id"],
                            f"migrated-{item['cycle_id']}" if article_title else None,
                            receipt.get("draft_media_id"),
                            receipt.get("title") or article_title,
                            receipt.get("transport"),
                            receipt.get("status") or "DRAFT_SAVED",
                            receipt_path,
                            receipt.get("saved_at_utc"),
                            (receipt.get("verification") or {}).get("status"),
                            timestamp,
                        ),
                    )

        current = state.get("current_cycle") or {}
        if current.get("cycle_id") and current.get("status") != "IDLE":
            selected_id = None
            if current.get("selected_doi"):
                selected_id = upsert_paper(
                    connection,
                    {"doi": current.get("selected_doi"), "title": current.get("selected_doi")},
                )
            timestamp = current.get("recommended_at") or state.get("updated_at") or now_iso()
            connection.execute(
                """
                INSERT INTO cycles(
                    cycle_id, status, candidate_pool_path, recommended_at,
                    selected_choice, selected_paper_id, selected_at, article_json_path,
                    preview_path, qa_status, user_draft_approval, draft_receipt_path,
                    created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cycle_id) DO NOTHING
                """,
                (
                    current["cycle_id"],
                    current["status"],
                    current.get("candidate_pool_path"),
                    current.get("recommended_at"),
                    current.get("selected_choice"),
                    selected_id,
                    current.get("selected_at"),
                    current.get("article_json_path"),
                    current.get("preview_path"),
                    current.get("qa_status"),
                    int(bool(current.get("user_draft_approval"))),
                    current.get("draft_receipt_path"),
                    timestamp,
                    state.get("updated_at") or timestamp,
                ),
            )
            counters["cycles"] += 1

        for item in registry.get("articles") or []:
            if not isinstance(item, dict):
                continue
            cycle_id = item.get("cycle_id")
            paper_id = upsert_paper(
                connection,
                {
                    "doi": item.get("doi"),
                    "title": item.get("source_title") or item.get("article_title") or "未知论文",
                },
            )
            if cycle_id:
                exists = connection.execute(
                    "SELECT 1 FROM cycles WHERE cycle_id=?", (cycle_id,)
                ).fetchone()
                if not exists:
                    timestamp = item.get("published_at") or now_iso()
                    connection.execute(
                        """
                        INSERT INTO cycles(
                            cycle_id, status, selected_paper_id, created_at, updated_at, completed_at
                        ) VALUES(?, 'PUBLISHED', ?, ?, ?, ?)
                        """,
                        (cycle_id, paper_id, timestamp, timestamp, timestamp),
                    )
            verification = item.get("verification") or {}
            publication_id = item.get("publication_id") or f"publication-{uuid.uuid4().hex}"
            timestamp = item.get("published_at") or now_iso()
            connection.execute(
                """
                INSERT INTO publications(
                    publication_id, cycle_id, paper_id, source_title, article_title,
                    public_url, published_at, verification_status,
                    verification_http_status, title_matched, publish_time_matched,
                    verified_at, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(publication_id) DO UPDATE SET
                    article_title=excluded.article_title,
                    public_url=excluded.public_url,
                    verification_status=excluded.verification_status,
                    updated_at=excluded.updated_at
                """,
                (
                    publication_id,
                    cycle_id,
                    paper_id,
                    item.get("source_title"),
                    item.get("article_title"),
                    item.get("public_url"),
                    timestamp,
                    verification.get("status"),
                    verification.get("http_status"),
                    int(bool(verification.get("title_matched"))),
                    int(bool(verification.get("publish_time_matched"))),
                    verification.get("verified_at"),
                    timestamp,
                    now_iso(),
                ),
            )
            if cycle_id:
                connection.execute(
                    "UPDATE cycles SET status='PUBLISHED', updated_at=?, completed_at=? WHERE cycle_id=?",
                    (now_iso(), timestamp, cycle_id),
                )
            counters["publications"] += 1
            for checkpoint in item.get("metric_snapshots") or []:
                connection.execute(
                    """
                    INSERT INTO metric_checkpoints(publication_id, label, due_at, status, source)
                    VALUES(?, ?, ?, ?, ?)
                    ON CONFLICT(publication_id, label) DO UPDATE SET
                        due_at=excluded.due_at, status=excluded.status, source=excluded.source
                    """,
                    (
                        publication_id,
                        checkpoint.get("label"),
                        checkpoint.get("due_at"),
                        checkpoint.get("status"),
                        checkpoint.get("source") or "wechat_backend_export",
                    ),
                )
                counters["checkpoints"] += 1
    export_compatibility(connection)
    return counters


def create_cycle(
    connection: sqlite3.Connection,
    cycle_id: str,
    recommendation_path: Path,
    recommended_at: str | None,
) -> int:
    payload = load_json(recommendation_path)
    timestamp = recommended_at or payload.get("generated_at") or now_iso()
    policy = recommendation_policy(connection)
    with immediate_transaction(connection):
        current = active_cycle(connection)
        if current:
            raise ValueError(
                f"已有未完成周期：{current['cycle_id']} ({current['status']})"
            )
        connection.execute(
            """
            INSERT INTO cycles(
                cycle_id, status, candidate_pool_path, recommended_at, created_at, updated_at
            ) VALUES(?, 'AWAITING_SELECTION', ?, ?, ?, ?)
            """,
            (cycle_id, str(recommendation_path), timestamp, timestamp, timestamp),
        )
        round_number = next_recommendation_round(connection)
        connection.execute(
            """
            INSERT INTO recommendation_rounds(cycle_id, round_number, created_at)
            VALUES(?, ?, ?)
            """,
            (cycle_id, round_number, timestamp),
        )
        count = insert_candidates(
            connection,
            cycle_id,
            payload,
            reject_previous=True,
            recommendation_round_number=round_number,
            cooldown_rounds=policy["unselected_cooldown_rounds"],
        )
    export_compatibility(connection)
    return count


def import_candidates(
    connection: sqlite3.Connection, cycle_id: str, recommendation_path: Path
) -> int:
    payload = load_json(recommendation_path)
    with immediate_transaction(connection):
        exists = connection.execute(
            "SELECT 1 FROM cycles WHERE cycle_id=?", (cycle_id,)
        ).fetchone()
        if not exists:
            raise ValueError(f"周期不存在：{cycle_id}")
        count = insert_candidates(connection, cycle_id, payload, reject_previous=False)
        connection.execute(
            "UPDATE cycles SET candidate_pool_path=COALESCE(candidate_pool_path, ?), updated_at=? WHERE cycle_id=?",
            (str(recommendation_path), now_iso(), cycle_id),
        )
    export_compatibility(connection)
    return count


def select_ordered_candidates(
    connection: sqlite3.Connection, choices: list[int], selected_at: str | None
) -> dict[str, Any]:
    if not choices:
        raise ValueError("至少需要选择一篇论文。")
    normalized_choices = [int(choice) for choice in choices]
    if len(set(normalized_choices)) != len(normalized_choices):
        raise ValueError("排序选择中不能包含重复序号。")
    timestamp = selected_at or now_iso()
    with immediate_transaction(connection):
        cycle = active_cycle(connection)
        if not cycle or cycle["status"] != "AWAITING_SELECTION":
            status = cycle["status"] if cycle else "IDLE"
            raise ValueError(f"当前状态不能选文：{status}")
        placeholders = ",".join("?" for _ in normalized_choices)
        candidates = connection.execute(
            f"""
            SELECT c.*, p.doi, p.pmid, p.title, p.journal
            FROM candidates c
            JOIN papers p ON p.paper_id=c.paper_id
            WHERE c.cycle_id=? AND c.choice IN ({placeholders})
            """,
            (cycle["cycle_id"], *normalized_choices),
        ).fetchall()
        by_choice = {int(candidate["choice"]): candidate for candidate in candidates}
        missing = [choice for choice in normalized_choices if choice not in by_choice]
        if missing:
            raise ValueError(f"候选序号不存在：{', '.join(map(str, missing))}")
        existing_queue = connection.execute(
            """
            SELECT 1 FROM selection_queue WHERE batch_cycle_id=? LIMIT 1
            """,
            (cycle["cycle_id"],),
        ).fetchone()
        if existing_queue:
            raise ValueError("当前推荐批次已经建立过处理队列。")
        first_choice = normalized_choices[0]
        first_candidate = by_choice[first_choice]
        connection.execute(
            """
            UPDATE cycles SET status='SELECTED', selected_choice=?, selected_paper_id=?,
                selected_at=?, updated_at=? WHERE cycle_id=? AND status='AWAITING_SELECTION'
            """,
            (
                first_choice,
                first_candidate["paper_id"],
                timestamp,
                timestamp,
                cycle["cycle_id"],
            ),
        )
        queue_items = []
        for position, choice in enumerate(normalized_choices, start=1):
            candidate = by_choice[choice]
            is_first = position == 1
            connection.execute(
                """
                INSERT INTO selection_queue(
                    batch_cycle_id, source_choice, paper_id, queue_position,
                    status, processing_cycle_id, queued_at, activated_at, available_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cycle["cycle_id"],
                    choice,
                    candidate["paper_id"],
                    position,
                    "ACTIVE" if is_first else "QUEUED",
                    cycle["cycle_id"] if is_first else None,
                    timestamp,
                    timestamp if is_first else None,
                    timestamp if is_first else None,
                ),
            )
            queue_items.append(
                {
                    "position": position,
                    "choice": choice,
                    "status": "ACTIVE" if is_first else "QUEUED",
                    "available_at": timestamp if is_first else None,
                    "doi": candidate["doi"],
                    "pmid": candidate["pmid"],
                    "title": candidate["title"],
                }
            )
        result = {
            "cycle_id": cycle["cycle_id"],
            "status": "SELECTED",
            "choice": first_choice,
            "doi": first_candidate["doi"],
            "title": first_candidate["title"],
            "selection_order": normalized_choices,
            "queue": queue_items,
        }
    export_compatibility(connection)
    return result


def select_candidate(
    connection: sqlite3.Connection, choice: int, selected_at: str | None
) -> dict[str, Any]:
    return select_ordered_candidates(connection, [choice], selected_at)


def advance_selection_queue(
    connection: sqlite3.Connection,
    completed_cycle_id: str,
    completed_item_status: str,
    timestamp: str,
) -> dict[str, Any] | None:
    if completed_item_status not in {"COMPLETED", "CANCELLED"}:
        raise ValueError("队列完成状态必须是 COMPLETED 或 CANCELLED。")
    active_item = connection.execute(
        """
        SELECT * FROM selection_queue
        WHERE processing_cycle_id=? AND status='ACTIVE'
        """,
        (completed_cycle_id,),
    ).fetchone()
    if not active_item:
        return None
    connection.execute(
        """
        UPDATE selection_queue
        SET status=?, completed_at=?
        WHERE queue_item_id=? AND status='ACTIVE'
        """,
        (completed_item_status, timestamp, active_item["queue_item_id"]),
    )
    next_item = connection.execute(
        """
        SELECT q.*, p.doi, p.pmid, p.title, p.journal
        FROM selection_queue q
        JOIN papers p ON p.paper_id=q.paper_id
        WHERE q.batch_cycle_id=? AND q.status='QUEUED'
        ORDER BY q.queue_position
        LIMIT 1
        """,
        (active_item["batch_cycle_id"],),
    ).fetchone()
    if not next_item:
        return None
    current = active_cycle(connection)
    if current:
        raise ValueError(
            f"无法推进排队论文，已有活动周期：{current['cycle_id']} ({current['status']})"
        )
    processing_cycle_id = (
        f"{active_item['batch_cycle_id']}-queue-{int(next_item['queue_position'])}"
    )
    existing = connection.execute(
        "SELECT 1 FROM cycles WHERE cycle_id=?", (processing_cycle_id,)
    ).fetchone()
    if existing:
        processing_cycle_id = f"{processing_cycle_id}-{uuid.uuid4().hex[:8]}"
    batch = connection.execute(
        "SELECT * FROM cycles WHERE cycle_id=?", (active_item["batch_cycle_id"],)
    ).fetchone()
    source_candidate = connection.execute(
        """
        SELECT * FROM candidates
        WHERE cycle_id=? AND choice=?
        """,
        (active_item["batch_cycle_id"], next_item["source_choice"]),
    ).fetchone()
    if not batch or not source_candidate:
        raise ValueError("排队论文缺少原始推荐批次或候选记录。")
    connection.execute(
        """
        INSERT INTO cycles(
            cycle_id, status, recommended_at, selected_choice, selected_paper_id,
            selected_at, created_at, updated_at
        ) VALUES(?, 'SELECTED', ?, ?, ?, ?, ?, ?)
        """,
        (
            processing_cycle_id,
            batch["recommended_at"],
            next_item["source_choice"],
            next_item["paper_id"],
            timestamp,
            timestamp,
            timestamp,
        ),
    )
    connection.execute(
        """
        INSERT INTO candidates(
            cycle_id, choice, paper_id, score, topic_tags_json,
            recommendation_reason, source_json
        ) VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        (
            processing_cycle_id,
            next_item["source_choice"],
            next_item["paper_id"],
            source_candidate["score"],
            source_candidate["topic_tags_json"],
            source_candidate["recommendation_reason"],
            source_candidate["source_json"],
        ),
    )
    available_at = next_queue_preparation_at(connection, timestamp)
    connection.execute(
        """
        UPDATE selection_queue
        SET status='ACTIVE', processing_cycle_id=?, activated_at=?, available_at=?
        WHERE queue_item_id=? AND status='QUEUED'
        """,
        (
            processing_cycle_id,
            timestamp,
            available_at,
            next_item["queue_item_id"],
        ),
    )
    return {
        "cycle_id": processing_cycle_id,
        "status": "SELECTED",
        "queue_position": int(next_item["queue_position"]),
        "choice": int(next_item["source_choice"]),
        "doi": next_item["doi"],
        "pmid": next_item["pmid"],
        "title": next_item["title"],
        "journal": next_item["journal"],
        "available_at": available_at,
    }


def claim_writing(
    connection: sqlite3.Connection,
    automation_id: str,
    run_key: str | None,
    claimed_at: str | None = None,
) -> dict[str, Any]:
    timestamp = claimed_at or now_iso()
    job_run_id = f"job-{uuid.uuid4().hex}"
    with immediate_transaction(connection):
        if run_key:
            previous = connection.execute(
                "SELECT * FROM job_runs WHERE run_key=?", (run_key,)
            ).fetchone()
            if previous:
                return {
                    "claimed": False,
                    "reason": "duplicate_run_key",
                    "job_run_id": previous["job_run_id"],
                    "cycle_id": previous["cycle_id"],
                }
        cycle = active_cycle(connection)
        if not cycle or cycle["status"] != "SELECTED":
            return {
                "claimed": False,
                "reason": "waiting_for_selection",
                "status": cycle["status"] if cycle else "IDLE",
            }
        queue_item = connection.execute(
            """
            SELECT available_at, queue_position
            FROM selection_queue
            WHERE processing_cycle_id=? AND status='ACTIVE'
            """,
            (cycle["cycle_id"],),
        ).fetchone()
        if queue_item and queue_item["available_at"]:
            current_time = datetime.fromisoformat(timestamp)
            available_time = datetime.fromisoformat(queue_item["available_at"])
            if current_time.tzinfo is None:
                current_time = current_time.replace(tzinfo=available_time.tzinfo)
            if available_time.tzinfo is None:
                available_time = available_time.replace(tzinfo=current_time.tzinfo)
            if current_time < available_time:
                return {
                    "claimed": False,
                    "reason": "queued_not_ready",
                    "status": "SELECTED",
                    "cycle_id": cycle["cycle_id"],
                    "queue_position": int(queue_item["queue_position"]),
                    "available_at": queue_item["available_at"],
                }
        updated = connection.execute(
            "UPDATE cycles SET status='WRITING', updated_at=? WHERE cycle_id=? AND status='SELECTED'",
            (timestamp, cycle["cycle_id"]),
        ).rowcount
        if updated != 1:
            raise RuntimeError("未能原子化领取写作任务。")
        connection.execute(
            """
            INSERT INTO job_runs(
                job_run_id, run_key, automation_id, job_kind, cycle_id,
                status, started_at
            ) VALUES(?, ?, ?, 'PREPARE_ARTICLE', ?, 'RUNNING', ?)
            """,
            (job_run_id, run_key, automation_id, cycle["cycle_id"], timestamp),
        )
        result = {
            "claimed": True,
            "job_run_id": job_run_id,
            "cycle": cycle_dict(
                connection,
                connection.execute(
                    "SELECT * FROM cycles WHERE cycle_id=?", (cycle["cycle_id"],)
                ).fetchone(),
            ),
        }
    export_compatibility(connection)
    return result


def transition_cycle(
    connection: sqlite3.Connection,
    cycle_id: str,
    expected_status: str,
    target_status: str,
    detail: str | None = None,
) -> dict[str, Any] | None:
    ensure_safe_text(detail, "transition.detail")
    if target_status not in ALLOWED_TRANSITIONS.get(expected_status, set()):
        raise ValueError(f"不允许的状态转换：{expected_status} -> {target_status}")
    timestamp = now_iso()
    completed_at = timestamp if target_status in TERMINAL_STATUSES else None
    next_queued = None
    with immediate_transaction(connection):
        updated = connection.execute(
            """
            UPDATE cycles SET status=?, updated_at=?, completed_at=COALESCE(?, completed_at)
            WHERE cycle_id=? AND status=?
            """,
            (target_status, timestamp, completed_at, cycle_id, expected_status),
        ).rowcount
        if updated != 1:
            row = connection.execute(
                "SELECT status FROM cycles WHERE cycle_id=?", (cycle_id,)
            ).fetchone()
            actual = row["status"] if row else "MISSING"
            raise ValueError(f"状态不匹配：期望 {expected_status}，实际 {actual}")
        if detail:
            set_metadata(connection, f"transition_detail:{cycle_id}:{timestamp}", detail)
        if target_status == "CANCELLED":
            next_queued = advance_selection_queue(
                connection, cycle_id, "CANCELLED", timestamp
            )
    export_compatibility(connection)
    return next_queued


def set_artifacts(
    connection: sqlite3.Connection,
    cycle_id: str,
    article_json_path: str,
    preview_path: str,
    qa_status: str,
) -> dict[str, Any]:
    if qa_status != "QA_PASSED":
        raise ValueError("只有 QA_PASSED 才能进入草稿审批阶段。")
    article_payload = load_json(Path(article_json_path))
    article_id = str(article_payload.get("article_id") or "").strip()
    title = str(article_payload.get("title") or "").strip()
    if not article_id or not title:
        raise ValueError("文章 JSON 缺少 article_id 或 title。")
    timestamp = now_iso()
    with immediate_transaction(connection):
        cycle = connection.execute(
            "SELECT * FROM cycles WHERE cycle_id=?", (cycle_id,)
        ).fetchone()
        if not cycle or cycle["status"] != "WRITING":
            raise ValueError(f"当前周期不在 WRITING：{cycle['status'] if cycle else 'MISSING'}")
        connection.execute(
            """
            INSERT INTO articles(
                article_id, cycle_id, source_paper_id, title, article_json_path,
                preview_path, qa_status, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cycle_id) DO UPDATE SET
                article_id=excluded.article_id,
                title=excluded.title,
                article_json_path=excluded.article_json_path,
                preview_path=excluded.preview_path,
                qa_status=excluded.qa_status,
                updated_at=excluded.updated_at
            """,
            (
                article_id,
                cycle_id,
                cycle["selected_paper_id"],
                title,
                article_json_path,
                preview_path,
                qa_status,
                timestamp,
                timestamp,
            ),
        )
        connection.execute(
            """
            UPDATE cycles SET status='AWAITING_DRAFT_APPROVAL', article_json_path=?,
                preview_path=?, qa_status=?, updated_at=?
            WHERE cycle_id=? AND status='WRITING'
            """,
            (article_json_path, preview_path, qa_status, timestamp, cycle_id),
        )
    export_compatibility(connection)
    return {"cycle_id": cycle_id, "status": "AWAITING_DRAFT_APPROVAL", "article_id": article_id}


def approve_draft(connection: sqlite3.Connection, cycle_id: str) -> None:
    with immediate_transaction(connection):
        updated = connection.execute(
            """
            UPDATE cycles SET user_draft_approval=1, updated_at=?
            WHERE cycle_id=? AND status='AWAITING_DRAFT_APPROVAL' AND qa_status='QA_PASSED'
            """,
            (now_iso(), cycle_id),
        ).rowcount
        if updated != 1:
            raise ValueError("草稿审批失败：周期状态或 QA 状态不满足要求。")
    export_compatibility(connection)


def record_draft(connection: sqlite3.Connection, cycle_id: str, receipt_path: Path) -> dict[str, Any]:
    receipt = load_json(receipt_path)
    if receipt.get("status") != "DRAFT_SAVED" or receipt.get("publication_mode") != "draft_only":
        raise ValueError("草稿回执必须为 DRAFT_SAVED 且 publication_mode=draft_only。")
    timestamp = now_iso()
    next_queued = None
    with immediate_transaction(connection):
        cycle = connection.execute(
            "SELECT * FROM cycles WHERE cycle_id=?", (cycle_id,)
        ).fetchone()
        if not cycle or cycle["status"] != "AWAITING_DRAFT_APPROVAL":
            raise ValueError("当前周期不在草稿审批阶段。")
        if not cycle["user_draft_approval"] or cycle["qa_status"] != "QA_PASSED":
            raise ValueError("缺少用户草稿批准或 QA_PASSED。")
        article = connection.execute(
            "SELECT * FROM articles WHERE cycle_id=?", (cycle_id,)
        ).fetchone()
        connection.execute(
            """
            INSERT INTO drafts(
                cycle_id, article_id, draft_media_id, title, transport, status,
                receipt_path, saved_at, verification_status, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(draft_media_id) DO UPDATE SET
                status=excluded.status, receipt_path=excluded.receipt_path,
                verification_status=excluded.verification_status
            """,
            (
                cycle_id,
                article["article_id"] if article else None,
                receipt.get("draft_media_id"),
                receipt.get("title"),
                receipt.get("transport"),
                receipt.get("status"),
                str(receipt_path),
                receipt.get("saved_at_utc"),
                (receipt.get("verification") or {}).get("status"),
                timestamp,
            ),
        )
        connection.execute(
            """
            UPDATE cycles SET status='DRAFT_SAVED', draft_receipt_path=?,
                updated_at=?, completed_at=? WHERE cycle_id=?
            """,
            (str(receipt_path), timestamp, timestamp, cycle_id),
        )
        next_queued = advance_selection_queue(
            connection, cycle_id, "COMPLETED", timestamp
        )
    export_compatibility(connection)
    return {
        "cycle_id": cycle_id,
        "status": "DRAFT_SAVED",
        "next_queued": next_queued,
    }


def record_publication(connection: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_safe_payload(payload)
    publication_id = str(payload.get("publication_id") or "").strip()
    public_url = str(payload.get("public_url") or "").strip()
    article_title = str(payload.get("article_title") or "").strip()
    published_at = str(payload.get("published_at") or "").strip()
    if not publication_id or not public_url or not article_title or not published_at:
        raise ValueError("发表记录缺少 publication_id、public_url、article_title 或 published_at。")
    cycle_id = str(payload.get("cycle_id") or "").strip() or None
    paper_id = upsert_paper(
        connection,
        {
            "doi": payload.get("doi"),
            "title": payload.get("source_title") or article_title,
        },
    )
    verification = payload.get("verification") or {}
    timestamp = now_iso()
    with immediate_transaction(connection):
        connection.execute(
            """
            INSERT INTO publications(
                publication_id, cycle_id, paper_id, source_title, article_title,
                public_url, published_at, verification_status,
                verification_http_status, title_matched, publish_time_matched,
                verified_at, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(publication_id) DO UPDATE SET
                article_title=excluded.article_title,
                public_url=excluded.public_url,
                verification_status=excluded.verification_status,
                updated_at=excluded.updated_at
            """,
            (
                publication_id,
                cycle_id,
                paper_id,
                payload.get("source_title"),
                article_title,
                public_url,
                published_at,
                verification.get("status"),
                verification.get("http_status"),
                int(bool(verification.get("title_matched"))),
                int(bool(verification.get("publish_time_matched"))),
                verification.get("verified_at"),
                timestamp,
                timestamp,
            ),
        )
        if cycle_id:
            connection.execute(
                """
                UPDATE cycles SET status='PUBLISHED', updated_at=?, completed_at=?
                WHERE cycle_id=? AND status IN ('DRAFT_SAVED','COMPLETED','PUBLISHED')
                """,
                (timestamp, published_at, cycle_id),
            )
        for checkpoint in payload.get("metric_snapshots") or []:
            connection.execute(
                """
                INSERT INTO metric_checkpoints(publication_id, label, due_at, status, source)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(publication_id, label) DO UPDATE SET
                    due_at=excluded.due_at, status=excluded.status, source=excluded.source
                """,
                (
                    publication_id,
                    checkpoint.get("label"),
                    checkpoint.get("due_at"),
                    checkpoint.get("status"),
                    checkpoint.get("source") or "wechat_backend_export",
                ),
            )
    export_compatibility(connection)
    return {"publication_id": publication_id, "status": "PUBLISHED"}


def record_stats(
    connection: sqlite3.Connection,
    publication_id: str,
    observed_at: str,
    metrics: dict[str, Any],
    source_path: str | None,
) -> dict[str, Any]:
    ensure_safe_payload(metrics)
    ensure_safe_text(source_path, "stats.source_path")
    allowed = {
        "reads",
        "readers",
        "shares",
        "sharers",
        "likes",
        "wows",
        "favorites",
        "comments",
        "delivered",
        "new_followers",
    }
    unknown = sorted(set(metrics) - allowed)
    if unknown:
        raise ValueError(f"不支持的统计字段：{', '.join(unknown)}")
    import_id = f"stats-{uuid.uuid4().hex}"
    timestamp = now_iso()
    with immediate_transaction(connection):
        publication = connection.execute(
            "SELECT 1 FROM publications WHERE publication_id=?", (publication_id,)
        ).fetchone()
        if not publication:
            raise ValueError(f"发表记录不存在：{publication_id}")
        connection.execute(
            """
            INSERT INTO stats_imports(import_id, imported_at, source_path, source_kind)
            VALUES(?, ?, ?, 'wechat_backend_export')
            """,
            (import_id, timestamp, source_path),
        )
        columns = [
            "reads", "readers", "shares", "sharers", "likes", "wows",
            "favorites", "comments", "delivered", "new_followers"
        ]
        values = [metrics.get(column) for column in columns]
        connection.execute(
            f"""
            INSERT INTO stats_snapshots(
                publication_id, import_id, observed_at, {', '.join(columns)}, raw_json
            ) VALUES(?, ?, ?, {', '.join('?' for _ in columns)}, ?)
            ON CONFLICT(publication_id, observed_at) DO UPDATE SET
                import_id=excluded.import_id,
                {', '.join(f'{column}=excluded.{column}' for column in columns)},
                raw_json=excluded.raw_json
            """,
            (
                publication_id,
                import_id,
                observed_at,
                *values,
                json.dumps(metrics, ensure_ascii=False),
            ),
        )
        connection.execute(
            """
            UPDATE metric_checkpoints SET status='COLLECTED'
            WHERE publication_id=? AND due_at<=? AND status<>'COLLECTED'
            """,
            (publication_id, observed_at),
        )
    export_compatibility(connection)
    return {"publication_id": publication_id, "observed_at": observed_at, "import_id": import_id}


def finish_job(
    connection: sqlite3.Connection, job_run_id: str, status: str, detail: str | None
) -> None:
    ensure_safe_text(detail, "job.detail")
    if status not in {"SUCCEEDED", "FAILED", "BLOCKED", "SKIPPED"}:
        raise ValueError("任务结束状态不受支持。")
    with immediate_transaction(connection):
        updated = connection.execute(
            """
            UPDATE job_runs SET status=?, finished_at=?, detail=?
            WHERE job_run_id=? AND status='RUNNING'
            """,
            (status, now_iso(), detail, job_run_id),
        ).rowcount
        if updated != 1:
            raise ValueError("任务运行记录不存在或已经结束。")


def check_database(connection: sqlite3.Connection) -> dict[str, Any]:
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    foreign_keys = [dict(row) for row in connection.execute("PRAGMA foreign_key_check")]
    counts = {}
    for table in (
        "papers", "cycles", "candidates", "articles", "drafts", "publications",
        "recommendation_rounds", "selection_queue", "metric_checkpoints",
        "stats_snapshots", "job_runs"
    ):
        counts[table] = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    queue_consistency_errors: list[str] = []
    active_queue_count = int(
        connection.execute(
            "SELECT COUNT(*) FROM selection_queue WHERE status='ACTIVE'"
        ).fetchone()[0]
    )
    if active_queue_count > 1:
        queue_consistency_errors.append(
            f"selection_queue 同时存在 {active_queue_count} 个 ACTIVE 项。"
        )
    orphaned_active = connection.execute(
        """
        SELECT q.queue_item_id
        FROM selection_queue q
        LEFT JOIN cycles c ON c.cycle_id=q.processing_cycle_id
        WHERE q.status='ACTIVE'
          AND (q.processing_cycle_id IS NULL OR c.cycle_id IS NULL OR c.status NOT IN (
              'SELECTED','WRITING','QA_PASSED','AWAITING_DRAFT_APPROVAL','EVIDENCE_BLOCKED'
          ))
        """
    ).fetchall()
    if orphaned_active:
        queue_consistency_errors.append(
            "ACTIVE 队列项未对应活动处理周期："
            + ", ".join(str(row["queue_item_id"]) for row in orphaned_active)
        )
    credential_key_violations: list[str] = []
    json_columns = (
        ("metadata", "key", "value_json"),
        ("candidates", "cycle_id || ':' || choice", "source_json"),
        ("stats_snapshots", "snapshot_id", "raw_json"),
    )
    for table, identifier_sql, column in json_columns:
        for row in connection.execute(
            f"SELECT {identifier_sql} AS identifier, {column} AS payload FROM {table}"
        ):
            try:
                ensure_safe_payload(json.loads(row["payload"]), f"{table}:{row['identifier']}")
            except (ValueError, json.JSONDecodeError) as exc:
                credential_key_violations.append(str(exc))
    return {
        "status": "OK"
        if integrity == "ok"
        and not foreign_keys
        and not credential_key_violations
        and not queue_consistency_errors
        else "FAILED",
        "integrity_check": integrity,
        "foreign_key_errors": foreign_keys,
        "credential_key_violations": credential_key_violations,
        "queue_consistency_errors": queue_consistency_errors,
        "counts": counts,
        "current_cycle": cycle_dict(connection, active_cycle(connection)),
        "selection_queue": selection_queue_status(connection),
        "recommendation_policy": recommendation_policy(connection),
    }


def parse_choice_order(value: str) -> list[int]:
    parts = [part.strip() for part in str(value).replace("，", ",").split(",")]
    if not parts or any(not part for part in parts):
        raise argparse.ArgumentTypeError("选择顺序应类似 2,3。")
    try:
        choices = [int(part) for part in parts]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("选择顺序只能包含整数序号。") from exc
    if any(choice <= 0 for choice in choices):
        raise argparse.ArgumentTypeError("候选序号必须为正整数。")
    return choices


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MRI 微信公众号工作流 SQLite 状态管理。")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init")
    migrate = subparsers.add_parser("migrate")
    migrate.add_argument("--state-json", type=Path, default=DEFAULT_STATE_JSON)
    migrate.add_argument("--publication-json", type=Path, default=DEFAULT_PUBLICATION_JSON)

    status = subparsers.add_parser("status")
    status.add_argument("--compact", action="store_true")

    create = subparsers.add_parser("create-cycle")
    create.add_argument("--cycle-id", required=True)
    create.add_argument("--recommendations-json", type=Path, required=True)
    create.add_argument("--recommended-at")

    import_cmd = subparsers.add_parser("import-candidates")
    import_cmd.add_argument("--cycle-id", required=True)
    import_cmd.add_argument("--recommendations-json", type=Path, required=True)

    select = subparsers.add_parser("select")
    select.add_argument("--choice", type=int, required=True)
    select.add_argument("--selected-at")

    select_order = subparsers.add_parser("select-order")
    select_order.add_argument("--choices", type=parse_choice_order, required=True)
    select_order.add_argument("--selected-at")

    exclusions = subparsers.add_parser("recommendation-exclusions")
    exclusions.add_argument("--cooldown-rounds", type=int)

    subparsers.add_parser("queue-status")

    claim = subparsers.add_parser("claim-writing")
    claim.add_argument("--automation-id", default="mri-09-30")
    claim.add_argument("--run-key")

    transition = subparsers.add_parser("transition")
    transition.add_argument("--cycle-id", required=True)
    transition.add_argument("--from-status", required=True, choices=sorted(ALL_STATUSES))
    transition.add_argument("--to-status", required=True, choices=sorted(ALL_STATUSES))
    transition.add_argument("--detail")

    artifacts = subparsers.add_parser("set-artifacts")
    artifacts.add_argument("--cycle-id", required=True)
    artifacts.add_argument("--article-json", required=True)
    artifacts.add_argument("--preview", required=True)
    artifacts.add_argument("--qa-status", required=True)

    approve = subparsers.add_parser("approve-draft")
    approve.add_argument("--cycle-id", required=True)

    draft = subparsers.add_parser("record-draft")
    draft.add_argument("--cycle-id", required=True)
    draft.add_argument("--receipt", type=Path, required=True)

    publication = subparsers.add_parser("record-publication")
    publication.add_argument("--json", type=Path, required=True)

    stats = subparsers.add_parser("record-stats")
    stats.add_argument("--publication-id", required=True)
    stats.add_argument("--observed-at", required=True)
    stats.add_argument("--metrics-json", type=Path, required=True)
    stats.add_argument("--source-path")

    finish = subparsers.add_parser("finish-job")
    finish.add_argument("--job-run-id", required=True)
    finish.add_argument("--status", required=True, choices=["SUCCEEDED", "FAILED", "BLOCKED", "SKIPPED"])
    finish.add_argument("--detail")

    subparsers.add_parser("export-json")
    subparsers.add_parser("check")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        connection = connect(args.db.resolve())
        initialize(connection)
        if args.command == "init":
            result: Any = {"status": "INITIALIZED", "database": str(args.db.resolve())}
        elif args.command == "migrate":
            result = {
                "status": "MIGRATED",
                **migrate_legacy(connection, args.state_json.resolve(), args.publication_json.resolve()),
            }
        elif args.command == "status":
            result = {
                "current_cycle": cycle_dict(connection, active_cycle(connection)),
                "selection_queue": selection_queue_status(connection),
                "recommendation_policy": recommendation_policy(connection),
                "history": history_rows(connection),
            }
        elif args.command == "create-cycle":
            result = {
                "status": "AWAITING_SELECTION",
                "cycle_id": args.cycle_id,
                "candidate_count": create_cycle(
                    connection,
                    args.cycle_id,
                    args.recommendations_json.resolve(),
                    args.recommended_at,
                ),
            }
        elif args.command == "import-candidates":
            result = {
                "status": "IMPORTED",
                "cycle_id": args.cycle_id,
                "candidate_count": import_candidates(
                    connection, args.cycle_id, args.recommendations_json.resolve()
                ),
            }
        elif args.command == "select":
            result = select_candidate(connection, args.choice, args.selected_at)
        elif args.command == "select-order":
            result = select_ordered_candidates(connection, args.choices, args.selected_at)
        elif args.command == "recommendation-exclusions":
            result = recommendation_exclusions(connection, args.cooldown_rounds)
        elif args.command == "queue-status":
            result = selection_queue_status(connection)
        elif args.command == "claim-writing":
            result = claim_writing(connection, args.automation_id, args.run_key)
        elif args.command == "transition":
            next_queued = transition_cycle(
                connection, args.cycle_id, args.from_status, args.to_status, args.detail
            )
            result = {
                "cycle_id": args.cycle_id,
                "status": args.to_status,
                "next_queued": next_queued,
            }
        elif args.command == "set-artifacts":
            result = set_artifacts(
                connection,
                args.cycle_id,
                args.article_json,
                args.preview,
                args.qa_status,
            )
        elif args.command == "approve-draft":
            approve_draft(connection, args.cycle_id)
            result = {"cycle_id": args.cycle_id, "user_draft_approval": True}
        elif args.command == "record-draft":
            result = record_draft(connection, args.cycle_id, args.receipt.resolve())
        elif args.command == "record-publication":
            result = record_publication(connection, load_json(args.json.resolve()))
        elif args.command == "record-stats":
            result = record_stats(
                connection,
                args.publication_id,
                args.observed_at,
                load_json(args.metrics_json.resolve()),
                args.source_path,
            )
        elif args.command == "finish-job":
            finish_job(connection, args.job_run_id, args.status, args.detail)
            result = {"job_run_id": args.job_run_id, "status": args.status}
        elif args.command == "export-json":
            result = {"status": "EXPORTED", **export_compatibility(connection)}
        elif args.command == "check":
            result = check_database(connection)
        else:
            raise AssertionError(f"未知命令：{args.command}")
        compact = bool(getattr(args, "compact", False))
        print(json.dumps(result, ensure_ascii=False, indent=None if compact else 2))
        return 0
    except (OSError, ValueError, sqlite3.Error, RuntimeError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {"status": "ERROR", "error": str(exc)}, ensure_ascii=False, indent=2
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
