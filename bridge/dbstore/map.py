"""MapEngine — نقشهٔ پیام‌ها: ردیف‌های دوطرفه برای ریپلای/ویرایش/حذف.

هر ردیف = (src پلتفرم/چت/پیام) ⇄ (dst پلتفرم/چت/پیام) با pair_id؛
``other_side`` از هر دو سرِ ردیف جست‌وجو می‌کند و یک‌بار خروجی می‌دهد.
"""
from __future__ import annotations


class MapEngine:
    """همهٔ عملیات جدول msg_map."""

    def __init__(self, engine) -> None:
        self.engine = engine

    def add(self, pair_id, src_platform, src_chat, src_msg,
            dst_platform, dst_chat, dst_msg) -> None:
        self.engine.execute(
            """INSERT INTO msg_map(pair_id, src_platform, src_chat, src_msg,
                                   dst_platform, dst_chat, dst_msg)
               VALUES(?,?,?,?,?,?,?)""",
            (pair_id, src_platform, str(src_chat), int(src_msg),
             dst_platform, str(dst_chat), int(dst_msg)),
        )

    def other_side(self, platform, chat, msg, pair_id=None):
        """پیام(های) معادل در سمت مقابل را برمی‌گرداند (حذف تکراری‌ها)."""
        chat = str(chat)
        q = """SELECT * FROM msg_map
               WHERE ((src_platform=? AND src_chat=? AND src_msg=?)
                  OR (dst_platform=? AND dst_chat=? AND dst_msg=?))"""
        args = [platform, chat, int(msg), platform, chat, int(msg)]
        if pair_id is not None:
            q += " AND pair_id=?"
            args.append(pair_id)
        rows = self.engine.query_all(q, tuple(args))
        out, seen = [], set()
        for r in rows:
            if (r["src_platform"] == platform and r["src_chat"] == chat
                    and r["src_msg"] == int(msg)):
                key = (r["dst_platform"], r["dst_chat"], r["dst_msg"], r["pair_id"])
                if key in seen:
                    continue
                seen.add(key)
                out.append({"platform": r["dst_platform"], "chat": r["dst_chat"],
                            "msg": r["dst_msg"], "pair_id": r["pair_id"],
                            "row_id": r["id"]})
            else:
                key = (r["src_platform"], r["src_chat"], r["src_msg"], r["pair_id"])
                if key in seen:
                    continue
                seen.add(key)
                out.append({"platform": r["src_platform"], "chat": r["src_chat"],
                            "msg": r["src_msg"], "pair_id": r["pair_id"],
                            "row_id": r["id"]})
        return out

    def remove_row(self, row_id: int) -> None:
        self.engine.execute("DELETE FROM msg_map WHERE id=?", (row_id,))

    def replace_dst(self, row_id, new_platform, new_chat, new_msg) -> None:
        """بعد از حذف+ارسال مجدد (ویرایش رسانه) نگاشت را به‌روز می‌کند."""
        self.engine.execute(
            "UPDATE msg_map SET dst_platform=?, dst_chat=?, dst_msg=? WHERE id=?",
            (new_platform, str(new_chat), int(new_msg), row_id),
        )
