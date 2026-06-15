from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
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

