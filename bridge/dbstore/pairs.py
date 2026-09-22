"""PairsEngine — CRUD جفت‌های کانال + جست‌وجوی جهت‌آگاه برای هر سمت mirror.

``pairs_for_tg`` فقط جفت‌های tg2bale/both را می‌دهد؛ ``pairs_for_bale`` فقط
bale2tg/both را (با یوزرنیمِ بدون حساسیت به حروف).
"""
from __future__ import annotations


class PairsEngine:
    """همهٔ عملیات جدول pairs."""

    def __init__(self, engine) -> None:
        self.engine = engine

    def add(self, tg_chat_id, tg_label, tg_username, bale_chat_id, bale_label,
            bale_username, mode) -> int:
        """ثبت جفت — مقادیر نرمال (int tg / str bale)؛ resolveهای async بیرون انجام شده‌اند."""
        cur = self.engine.execute(
            """INSERT INTO pairs(tg_chat_id, tg_label, tg_username,
                                 bale_chat_id, bale_label, bale_username, mode)
               VALUES(?,?,?,?,?,?,?)""",
            (int(tg_chat_id), tg_label or "", tg_username or "",
             str(bale_chat_id), bale_label or "", bale_username or "", mode),
        )
        return cur.lastrowid

    def remove(self, pair_id: int) -> bool:
        """حذف جفت + همهٔ نگاشت‌هایش (یک تراکنش)."""
        with self.engine.lock:
            cur = self.engine.conn.execute("DELETE FROM pairs WHERE id=?", (pair_id,))
            self.engine.conn.execute("DELETE FROM msg_map WHERE pair_id=?", (pair_id,))
            self.engine.conn.commit()
            return cur.rowcount > 0

    def list(self):
        return self.engine.query_all("SELECT * FROM pairs ORDER BY id")

    def get(self, pair_id: int):
        return self.engine.query_one("SELECT * FROM pairs WHERE id=?", (pair_id,))

    def set_mode(self, pair_id: int, mode: str) -> bool:
        cur = self.engine.execute("UPDATE pairs SET mode=? WHERE id=?", (mode, pair_id))
        return cur.rowcount > 0

    def for_tg(self, tg_chat_id):
        """جفت‌های فعال در جهت تلگرام→بله برای این چت تلگرام."""
        return self.engine.query_all(
            "SELECT * FROM pairs WHERE tg_chat_id=? AND mode IN ('tg2bale','both')",
            (int(tg_chat_id),),
        )

    def for_bale(self, bale_chat_id, bale_username: str | None = None):
        """جفت‌های فعال در جهت بله→تلگرام — با شناسه یا یوزرنیم (بدون حساسیت به حروف)."""
        q = "SELECT * FROM pairs WHERE (bale_chat_id=?"
        args = [str(bale_chat_id)]
        if bale_username:
            q += " OR (bale_username<>'' AND lower(bale_username)=lower(?))"
            args.append(bale_username.lstrip("@"))
        q += ") AND mode IN ('bale2tg','both')"
        return self.engine.query_all(q, tuple(args))
