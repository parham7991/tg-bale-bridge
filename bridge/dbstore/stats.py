"""StatsEngine — شمارنده‌های وضعیت: جفت‌ها و پیام‌های نگاشت‌شده."""
from __future__ import annotations


class StatsEngine:
    """آمار سبک برای /status و داشبورد."""

    def __init__(self, engine) -> None:
        self.engine = engine

    def stats(self) -> dict:
        pairs = self.engine.query_one("SELECT COUNT(*) AS n FROM pairs")["n"]
        mapped = self.engine.query_one("SELECT COUNT(*) AS n FROM msg_map")["n"]
        return {"pairs": pairs, "mapped": mapped}
