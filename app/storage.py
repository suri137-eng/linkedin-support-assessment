"""SQLite persistence for sessions, messages, and hidden scores."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from . import config


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                candidate_name TEXT,
                candidate_linkedin TEXT,
                category_id TEXT,
                category_title TEXT,
                sub_id TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT,
                submitted_at TEXT,
                overall REAL,
                band TEXT,
                score_json TEXT
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                created_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
            """
        )
        # Migrate legacy DBs: candidate_email -> candidate_linkedin.
        cols = {r["name"] for r in c.execute("PRAGMA table_info(sessions)").fetchall()}
        if "candidate_email" in cols and "candidate_linkedin" not in cols:
            c.execute("ALTER TABLE sessions RENAME COLUMN candidate_email TO candidate_linkedin")


def create_session(
    candidate_name: str,
    linkedin_url: str,
    category_id: str,
    category_title: str,
    sub_id: str,
) -> str:
    sid = uuid.uuid4().hex
    with _conn() as c:
        c.execute(
            """INSERT INTO sessions
               (id, candidate_name, candidate_linkedin, category_id, category_title, sub_id, status, created_at)
               VALUES (?,?,?,?,?,?, 'active', ?)""",
            (sid, candidate_name, linkedin_url, category_id, category_title, sub_id, _now()),
        )
    return sid


def get_session(session_id: str) -> dict[str, Any] | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return dict(row) if row else None


def add_message(session_id: str, role: str, content: str) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
            (session_id, role, content, _now()),
        )


def get_history(session_id: str) -> list[dict[str, str]]:
    with _conn() as c:
        rows = c.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]


def count_candidate_turns(session_id: str) -> int:
    with _conn() as c:
        row = c.execute(
            "SELECT COUNT(*) AS n FROM messages WHERE session_id = ? AND role = 'candidate'",
            (session_id,),
        ).fetchone()
        return int(row["n"])


def mark_submitted(session_id: str, score: dict[str, Any]) -> None:
    with _conn() as c:
        c.execute(
            """UPDATE sessions
               SET status='submitted', submitted_at=?, overall=?, band=?, score_json=?
               WHERE id=?""",
            (_now(), score.get("overall"), score.get("band"), json.dumps(score), session_id),
        )


def list_results() -> list[dict[str, Any]]:
    with _conn() as c:
        rows = c.execute(
            """SELECT id, candidate_name, candidate_linkedin, category_title, sub_id,
                      status, created_at, submitted_at, overall, band
               FROM sessions ORDER BY created_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]


def get_result_detail(session_id: str) -> dict[str, Any] | None:
    session = get_session(session_id)
    if not session:
        return None
    history = get_history(session_id)
    score = json.loads(session["score_json"]) if session.get("score_json") else None
    return {"session": session, "history": history, "score": score}
