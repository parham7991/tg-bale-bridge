"""MetaEngine — جدول کلید/مقدار عمومی: آفست‌ها، pause، اکانت‌ها و…"""
from __future__ import annotations


class MetaEngine:
    """get/set ساده با upsert."""

    def __init__(self, engine) -> None:
        self.engine = engine     # ConnectionEngine

    def get(self, k: str, default: str | None = None):
        row = self.engine.query_one("SELECT v FROM meta WHERE k=?", (k,))
        return row["v"] if row else default

    def set(self, k: str, v: str) -> None:
        self.engine.execute(
            "INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
            (k, v),
        )
