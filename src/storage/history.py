"""
Persistent history and audit log manager using SQLite.
Stores every rename operation to enable safe, verified undo functionality.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from src.core.models import RenameHistoryRecord
from src.utils.platform_utils import get_app_data_dir


class HistoryManager:
    """Manages persistent audit records of all file renames in a SQLite database."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path:
            self.db_path = db_path
        else:
            self.db_path = get_app_data_dir() / "history.sqlite3"

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    from contextlib import contextmanager

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initializes tables for sessions and individual file renames."""
        with self._connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    folder_path TEXT NOT NULL,
                    total_files INTEGER NOT NULL,
                    renamed_files INTEGER NOT NULL,
                    is_reverted INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rename_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    original_path TEXT NOT NULL,
                    new_path TEXT NOT NULL,
                    original_name TEXT NOT NULL,
                    new_name TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    sha256 TEXT,
                    status TEXT NOT NULL,
                    error TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            conn.commit()

    def record_session(
        self,
        session_id: str,
        folder_path: str,
        total_files: int,
        records: List[RenameHistoryRecord]
    ) -> None:
        """Saves a complete rename session and its associated records."""
        renamed_count = sum(1 for r in records if r.status == "RENAMED")
        now_iso = datetime.now().isoformat()

        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions (session_id, timestamp, folder_path, total_files, renamed_files, is_reverted)
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                (session_id, now_iso, folder_path, total_files, renamed_count)
            )

            for r in records:
                conn.execute(
                    """
                    INSERT INTO rename_records (
                        session_id, timestamp, original_path, new_path,
                        original_name, new_name, file_size, sha256, status, error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        r.session_id, r.timestamp, r.original_path, r.new_path,
                        r.original_name, r.new_name, r.file_size, r.sha256, r.status, r.error
                    )
                )
            conn.commit()

    def get_recent_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Returns the most recent rename sessions."""
        with self._connection() as conn:
            cursor = conn.execute(
                """
                SELECT session_id, timestamp, folder_path, total_files, renamed_files, is_reverted
                FROM sessions
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_session_records(self, session_id: str) -> List[RenameHistoryRecord]:
        """Fetches all rename records for a given session."""
        with self._connection() as conn:
            cursor = conn.execute(
                """
                SELECT session_id, timestamp, original_path, new_path,
                       original_name, new_name, file_size, sha256, status, error
                FROM rename_records
                WHERE session_id = ?
                """,
                (session_id,)
            )
            rows = cursor.fetchall()
            return [
                RenameHistoryRecord(
                    session_id=row["session_id"],
                    timestamp=row["timestamp"],
                    original_path=row["original_path"],
                    new_path=row["new_path"],
                    original_name=row["original_name"],
                    new_name=row["new_name"],
                    file_size=row["file_size"],
                    sha256=row["sha256"],
                    status=row["status"],
                    error=row["error"],
                )
                for row in rows
            ]

    def mark_session_reverted(self, session_id: str) -> None:
        """Marks a session as reverted."""
        with self._connection() as conn:
            conn.execute(
                "UPDATE sessions SET is_reverted = 1 WHERE session_id = ?",
                (session_id,)
            )
            conn.execute(
                "UPDATE rename_records SET status = 'REVERTED' WHERE session_id = ? AND status = 'RENAMED'",
                (session_id,)
            )
            conn.commit()

    def get_last_active_session_id(self) -> Optional[str]:
        """Gets the session_id of the most recent session that hasn't been reverted."""
        with self._connection() as conn:
            cursor = conn.execute(
                """
                SELECT session_id FROM sessions
                WHERE is_reverted = 0 AND renamed_files > 0
                ORDER BY timestamp DESC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            return row["session_id"] if row else None
