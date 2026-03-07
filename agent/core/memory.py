"""
core/memory.py — SQLite-backed conversation history.
Thread-safe (WAL mode). Persists across restarts.
"""
from __future__ import annotations
import sqlite3
import datetime
from typing import List, Dict

import config


class Memory:
    def __init__(self, db_path: str = config.MEMORY_DB):
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS turns (
                    id    INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts    TEXT    NOT NULL,
                    user  TEXT    NOT NULL,
                    agent TEXT    NOT NULL
                )
            """)
            conn.commit()

    # ── Public API ───────────────────────────────────────────────────
    def save(self, user: str, agent: str):
        ts = datetime.datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO turns (ts, user, agent) VALUES (?, ?, ?)",
                (ts, user, agent),
            )
            conn.commit()

    def recent(self, n: int = 10) -> List[Dict]:
        """Return n most-recent turns, oldest first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT ts, user, agent FROM turns ORDER BY id DESC LIMIT ?", (n,)
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0]

    def summary_context(self, n: int = 5) -> str:
        """Short text block of recent turns for the planner prompt."""
        turns = self.recent(n)
        if not turns:
            return ""
        lines = []
        for t in turns:
            lines.append(f"User: {t['user']}")
            lines.append(f"Samantha: {t['agent']}")
        return "\n".join(lines)

    def clear(self):
        with self._connect() as conn:
            conn.execute("DELETE FROM turns")
            conn.commit()
