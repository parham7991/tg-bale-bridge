"""ConnectionEngine — اتصال SQLite، قفل نخ (RLock)، اجرای SCHEMA و commit.

تنها نقطهٔ تماس با sqlite3؛ بقیهٔ موتورها از ``engine.execute`` استفاده می‌کنند
تا قفل و connection یکتا بماند.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any


class ConnectionEngine:
    """مالک اتصال و قفل — با check_same_thread=False برای استفادهٔ چندنخی."""

    def __init__(self, path: str | Path, schema: str) -> None:
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(schema)
            self._conn.commit()

    # ───────────────────────────── اجرا ─────────────────────────────
    def execute(self, sql: str, args: tuple = ()) -> Any:
        """یک دستور + commit داخل قفل — cursor را برمی‌گرداند."""
        with self._lock:
            cur = self._conn.execute(sql, args)
            self._conn.commit()
            return cur

    def executemany(self, sql: str, seq) -> Any:
        with self._lock:
            cur = self._conn.executemany(sql, seq)
            self._conn.commit()
            return cur

    def query_all(self, sql: str, args: tuple = ()) -> list:
        """SELECT داخل قفل — نتیجه به‌صورت دیکشنری."""
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]

    def query_one(self, sql: str, args: tuple = ()):
        """SELECT تک‌ردیفی — دیکشنری یا None."""
        with self._lock:
            row = self._conn.execute(sql, args).fetchone()
        return dict(row) if row else None

    @property
    def conn(self):
        """دسترسی خام (برای تست‌ها و migrate) — همیشه با RLock استفاده شود."""
        return self._conn

    @property
    def lock(self):
        return self._lock

    def close(self) -> None:
        with self._lock:
            self._conn.close()
