from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterator


class Storage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    first_name TEXT,
                    water_norm_ml INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS weights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    measured_at TEXT NOT NULL,
                    weight_kg REAL NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                );

                CREATE TABLE IF NOT EXISTS water_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    logged_at TEXT NOT NULL,
                    amount_ml INTEGER NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                );

                CREATE TABLE IF NOT EXISTS user_state (
                    user_id INTEGER PRIMARY KEY,
                    state TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(users)").fetchall()
            }
            if "target_weight_kg" not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN target_weight_kg REAL")

    def upsert_user(
        self,
        user_id: int,
        first_name: str | None,
        water_norm_ml: int,
        now: datetime,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, first_name, water_norm_ml, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    first_name = excluded.first_name
                """,
                (user_id, first_name, water_norm_ml, now.isoformat()),
            )

    def users(self) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()

    def get_user(self, user_id: int) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()

    def set_state(self, user_id: int, state: str, now: datetime) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO user_state (user_id, state, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    state = excluded.state,
                    updated_at = excluded.updated_at
                """,
                (user_id, state, now.isoformat()),
            )

    def pop_state(self, user_id: int) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT state FROM user_state WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            conn.execute("DELETE FROM user_state WHERE user_id = ?", (user_id,))
            return row["state"] if row else None

    def add_weight(self, user_id: int, weight_kg: float, now: datetime) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO weights (user_id, measured_at, weight_kg) VALUES (?, ?, ?)",
                (user_id, now.isoformat(), weight_kg),
            )

    def add_water(self, user_id: int, amount_ml: int, now: datetime) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO water_logs (user_id, logged_at, amount_ml) VALUES (?, ?, ?)",
                (user_id, now.isoformat(), amount_ml),
            )

    def set_target_weight(self, user_id: int, target_weight_kg: float | None) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE users SET target_weight_kg = ? WHERE user_id = ?",
                (target_weight_kg, user_id),
            )

    def all_weights(self, user_id: int | None = None) -> list[sqlite3.Row]:
        query = "SELECT * FROM weights"
        params: tuple[int, ...] = ()
        if user_id is not None:
            query += " WHERE user_id = ?"
            params = (user_id,)
        query += " ORDER BY measured_at"
        with self.connect() as conn:
            return conn.execute(query, params).fetchall()

    def all_water_logs(self, user_id: int | None = None) -> list[sqlite3.Row]:
        query = "SELECT * FROM water_logs"
        params: tuple[int, ...] = ()
        if user_id is not None:
            query += " WHERE user_id = ?"
            params = (user_id,)
        query += " ORDER BY logged_at"
        with self.connect() as conn:
            return conn.execute(query, params).fetchall()

    def today_water_total(self, user_id: int, today: date) -> int:
        start = datetime.combine(today, datetime.min.time()).isoformat()
        end = datetime.combine(today, datetime.max.time()).isoformat()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(amount_ml), 0) AS total
                FROM water_logs
                WHERE user_id = ? AND logged_at BETWEEN ? AND ?
                """,
                (user_id, start, end),
            ).fetchone()
            return int(row["total"])

    def water_total_between(self, user_id: int, start: datetime, end: datetime) -> int:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(amount_ml), 0) AS total
                FROM water_logs
                WHERE user_id = ? AND logged_at >= ? AND logged_at < ?
                """,
                (user_id, start.isoformat(), end.isoformat()),
            ).fetchone()
            return int(row["total"])

    def weight_stats_between(self, user_id: int, start: datetime, end: datetime) -> sqlite3.Row:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT
                    AVG(weight_kg) AS average,
                    MIN(weight_kg) AS minimum,
                    MAX(weight_kg) AS maximum,
                    COUNT(*) AS count
                FROM weights
                WHERE user_id = ? AND measured_at >= ? AND measured_at < ?
                """,
                (user_id, start.isoformat(), end.isoformat()),
            ).fetchone()

    def average_weight_since(self, user_id: int, now: datetime, days: int) -> float | None:
        start = now - timedelta(days=days)
        row = self.weight_stats_between(user_id, start, now)
        return round(float(row["average"]), 2) if row["average"] is not None else None

    def average_weight_between(self, user_id: int, start: datetime, end: datetime) -> float | None:
        row = self.weight_stats_between(user_id, start, end)
        return round(float(row["average"]), 2) if row["average"] is not None else None

    def latest_weights(self, user_id: int, limit: int = 2) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT * FROM weights
                WHERE user_id = ?
                ORDER BY measured_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()

    def first_weight_between(self, user_id: int, start: datetime, end: datetime) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT * FROM weights
                WHERE user_id = ? AND measured_at >= ? AND measured_at < ?
                ORDER BY measured_at ASC
                LIMIT 1
                """,
                (user_id, start.isoformat(), end.isoformat()),
            ).fetchone()

    def last_weight_between(self, user_id: int, start: datetime, end: datetime) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT * FROM weights
                WHERE user_id = ? AND measured_at >= ? AND measured_at < ?
                ORDER BY measured_at DESC
                LIMIT 1
                """,
                (user_id, start.isoformat(), end.isoformat()),
            ).fetchone()

    def undo_last_entry(self, user_id: int) -> tuple[str, float | int, str] | None:
        with self.connect() as conn:
            weight = conn.execute(
                """
                SELECT id, measured_at AS created_at, weight_kg AS value
                FROM weights
                WHERE user_id = ?
                ORDER BY measured_at DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            water = conn.execute(
                """
                SELECT id, logged_at AS created_at, amount_ml AS value
                FROM water_logs
                WHERE user_id = ?
                ORDER BY logged_at DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()

            if not weight and not water:
                return None

            if weight and (not water or weight["created_at"] >= water["created_at"]):
                conn.execute("DELETE FROM weights WHERE id = ?", (weight["id"],))
                return ("weight", float(weight["value"]), weight["created_at"])

            conn.execute("DELETE FROM water_logs WHERE id = ?", (water["id"],))
            return ("water", int(water["value"]), water["created_at"])
