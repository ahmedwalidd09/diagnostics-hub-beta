import sqlite3
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from app.constants import DB_PATH

logger = logging.getLogger(__name__)


class Database:
    """SQLite wrapper for Diagnostics Hub data storage."""

    def __init__(self, db_path=DB_PATH):
        self.db_path = str(db_path)
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Create tables if they do not exist."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Scan history table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS scan_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        score INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        category_scores TEXT NOT NULL,
                        findings TEXT NOT NULL,
                        recommendations TEXT NOT NULL
                    )
                """)

                # Key-value settings table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                """)

                # Memory baseline telemetry
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS memory_baselines (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        total_mb REAL NOT NULL,
                        used_mb REAL NOT NULL,
                        free_mb REAL NOT NULL
                    )
                """)

                # Startup changes log for undo
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS startup_changes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        name TEXT NOT NULL,
                        source TEXT NOT NULL,
                        previous_state TEXT NOT NULL,
                        new_state TEXT NOT NULL
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")

    def save_scan_result(
        self,
        score: int,
        status: str,
        category_scores: Dict[str, Any],
        findings: Dict[str, Any],
        recommendations: List[str]
    ) -> int:
        """Insert a completed diagnostic scan into scan_history."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO scan_history (timestamp, score, status, category_scores, findings, recommendations)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    score,
                    status,
                    json.dumps(category_scores),
                    json.dumps(findings),
                    json.dumps(recommendations)
                )
            )
            conn.commit()
            return cursor.lastrowid or 0

    def get_scan_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent scan history ordered by date descending."""
        results = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, timestamp, score, status, category_scores, findings, recommendations
                    FROM scan_history
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,)
                )
                for row in cursor.fetchall():
                    results.append({
                        "id": row["id"],
                        "timestamp": row["timestamp"],
                        "score": row["score"],
                        "status": row["status"],
                        "category_scores": json.loads(row["category_scores"] or "{}"),
                        "findings": json.loads(row["findings"] or "{}"),
                        "recommendations": json.loads(row["recommendations"] or "[]"),
                    })
        except Exception as e:
            logger.error(f"Error fetching scan history: {e}")
        return results

    def clear_scan_history(self) -> None:
        """Clear all entries in scan_history."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM scan_history")
            conn.commit()

    def log_startup_change(
        self,
        name: str,
        source: str,
        previous_state: str,
        new_state: str
    ) -> int:
        """Log a change made to a startup program."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO startup_changes (timestamp, name, source, previous_state, new_state)
                VALUES (?, ?, ?, ?, ?)
                """,
                (now, name, source, previous_state, new_state)
            )
            conn.commit()
            return cursor.lastrowid or 0

    def get_last_startup_change(self) -> Optional[Dict[str, Any]]:
        """Get the most recent startup change for undo."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, timestamp, name, source, previous_state, new_state
                FROM startup_changes
                ORDER BY id DESC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def delete_startup_change(self, change_id: int) -> None:
        """Remove a change record after undo."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM startup_changes WHERE id = ?", (change_id,))
            conn.commit()

    def get_startup_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get startup modifications log."""
        results = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, timestamp, name, source, previous_state, new_state
                    FROM startup_changes
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,)
                )
                for row in cursor.fetchall():
                    results.append(dict(row))
        except Exception as e:
            logger.error(f"Error fetching startup history: {e}")
        return results

    def record_memory_baseline(self, total_mb: float, used_mb: float, free_mb: float) -> None:
        """Record system RAM telemetry baseline."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO memory_baselines (timestamp, total_mb, used_mb, free_mb)
                    VALUES (?, ?, ?, ?)
                    """,
                    (now, total_mb, used_mb, free_mb)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error recording memory baseline: {e}")

    def export_all_data(self) -> Dict[str, Any]:
        """Export all data from SQLite for user backup."""
        return {
            "scan_history": self.get_scan_history(1000),
            "startup_changes": self.get_startup_history(1000),
            "export_timestamp": datetime.now().isoformat()
        }


# Singleton database instance
db = Database()
