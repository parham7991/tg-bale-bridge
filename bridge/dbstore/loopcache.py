"""LoopCacheEngine — دو لایهٔ ضدلوپ ماندگار: دفترچهٔ sent (یک‌بارمصرف) و sent_fp (پنجره‌ای)."""
from __future__ import annotations

import time

from .types_map import CACHE_MAX_AGE


class LoopCacheEngine:
    """دفترچه‌های ضدلوپ — مصرفِ یک‌بارمصرف، پژواک را قطعی می‌بندد."""

    def __init__(self, engine) -> None:
        self.engine = engine

    # ───────────────────── دفترچهٔ sent (لایهٔ ۱) ─────────────────────
    def mark_sent(self, platform, chat, msg) -> None:
        self.engine.execute(
            "INSERT INTO sent(platform, chat, msg, created_at) VALUES(?,?,?,?)",
            (platform, str(chat), int(msg), time.time()),
        )

    def was_sent(self, platform, chat, msg) -> bool:
        """اگر پیام توسط خود پل ساخته شده True و رد آن پاک می‌شود."""
        row = self.engine.query_one(
            "SELECT id FROM sent WHERE platform=? AND chat=? AND msg=?",
            (platform, str(chat), int(msg)),
        )
        if row:
            self.engine.execute("DELETE FROM sent WHERE id=?", (row["id"],))
            return True
        return False

    # ───────────────────── اثر انگشت (لایهٔ ۲) ─────────────────────
    def add_fp(self, platform, chat, fp) -> None:
        self.engine.execute(
            "INSERT INTO sent_fp(platform, chat, fp, created_at) VALUES(?,?,?,?)",
            (platform, str(chat), fp, time.time()),
        )

    def check_fp(self, platform, chat, fp, window: float = 60.0) -> bool:
        """فقط داخل پنجرهٔ زمانی؛ مصرفِ یک‌بارمصرف."""
        row = self.engine.query_one(
            "SELECT id FROM sent_fp WHERE platform=? AND chat=? AND fp=? AND created_at>?",
            (platform, str(chat), fp, time.time() - window),
        )
        if row:
            self.engine.execute("DELETE FROM sent_fp WHERE id=?", (row["id"],))
            return True
        return False

    # ───────────────────── پاک‌سازی دوره‌ای ─────────────────────
    def prune(self, max_age: float = CACHE_MAX_AGE) -> None:
        cutoff = time.time() - max_age
        with self.engine.lock:
            self.engine.conn.execute("DELETE FROM sent WHERE created_at<?", (cutoff,))
            self.engine.conn.execute("DELETE FROM sent_fp WHERE created_at<?", (cutoff,))
            self.engine.conn.commit()
