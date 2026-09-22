"""DB — نمای سازگاری لایهٔ داده (ریشهٔ ترکیب بستهٔ dbstore).

سطح عمومی دقیقاً مثل قبل: ``DB(path)`` با همهٔ متدهای قبلی
(``get_meta/set_meta``, CRUD جفت‌ها, ``other_side``, ``mark_sent/was_sent``,
``add_fp/check_fp``, ``prune_caches``, ``stats``, …) — اما داخل، هر بخش به
موتور خودش تفویض می‌شود:

    types_map.py   → SCHEMA + ثابت‌ها      · connection.py → ConnectionEngine
    meta.py        → MetaEngine            · pairs.py      → PairsEngine
    map.py         → MapEngine             · loopcache.py  → LoopCacheEngine
    stats.py       → StatsEngine

نکتهٔ سازگاری: ``db._conn`` و ``db._lock`` همچنان در دسترس‌اند (پراپرتی زندهٔ
اتصال/قفل واقعی) — تست‌ها و مهاجرت‌های دستی نمی‌شکنند.
"""
from __future__ import annotations

from pathlib import Path

from .connection import ConnectionEngine
from .loopcache import LoopCacheEngine
from .map import MapEngine
from .meta import MetaEngine
from .pairs import PairsEngine
from .stats import StatsEngine
from .types_map import SCHEMA, VALID_MODES


class DB:
    """ذخیره‌سازی وضعیت: جفت‌های کانال، نگاشت پیام‌ها و جلوگیری از حلقه."""

    def __init__(self, path: str | Path):
        # ── موتورها ──
        self.engine = ConnectionEngine(path, SCHEMA)
        self.meta_engine = MetaEngine(self.engine)
        self.pairs_engine = PairsEngine(self.engine)
        self.map_engine = MapEngine(self.engine)
        self.loop_engine = LoopCacheEngine(self.engine)
        self.stats_engine = StatsEngine(self.engine)
        self.prune_caches()

    # ---------- سازگاری: اتصال و قفل ----------
    @property
    def _conn(self):
        return self.engine.conn

    @property
    def _lock(self):
        return self.engine.lock

    # ---------- متا ----------
    def get_meta(self, k: str, default: str | None = None):
        return self.meta_engine.get(k, default)

    def set_meta(self, k: str, v: str):
        self.meta_engine.set(k, v)

    # ---------- جفت‌ها ----------
    def add_pair(self, tg_chat_id, tg_label, tg_username, bale_chat_id,
                 bale_label, bale_username, mode) -> int:
        return self.pairs_engine.add(
            tg_chat_id, tg_label, tg_username, bale_chat_id, bale_label,
            bale_username, mode)

    def remove_pair(self, pair_id: int) -> bool:
        return self.pairs_engine.remove(pair_id)

    def list_pairs(self):
        return self.pairs_engine.list()

    def get_pair(self, pair_id: int):
        return self.pairs_engine.get(pair_id)

    def set_mode(self, pair_id: int, mode: str) -> bool:
        return self.pairs_engine.set_mode(pair_id, mode)

    def pairs_for_tg(self, tg_chat_id):
        return self.pairs_engine.for_tg(tg_chat_id)

    def pairs_for_bale(self, bale_chat_id, bale_username: str | None = None):
        return self.pairs_engine.for_bale(bale_chat_id, bale_username)

    # ---------- نگاشت پیام ----------
    def add_map(self, pair_id, src_platform, src_chat, src_msg,
                dst_platform, dst_chat, dst_msg):
        self.map_engine.add(pair_id, src_platform, src_chat, src_msg,
                            dst_platform, dst_chat, dst_msg)

    def other_side(self, platform, chat, msg, pair_id=None):
        return self.map_engine.other_side(platform, chat, msg, pair_id)

    def remove_map_row(self, row_id: int):
        self.map_engine.remove_row(row_id)

    def replace_map_dst(self, row_id, new_platform, new_chat, new_msg):
        self.map_engine.replace_dst(row_id, new_platform, new_chat, new_msg)

    # ---------- جلوگیری از حلقه ----------
    def mark_sent(self, platform, chat, msg):
        self.loop_engine.mark_sent(platform, chat, msg)

    def was_sent(self, platform, chat, msg) -> bool:
        return self.loop_engine.was_sent(platform, chat, msg)

    def add_fp(self, platform, chat, fp):
        self.loop_engine.add_fp(platform, chat, fp)

    def check_fp(self, platform, chat, fp, window: float = 60.0) -> bool:
        return self.loop_engine.check_fp(platform, chat, fp, window)

    def prune_caches(self, max_age: float = None):
        if max_age is None:
            self.loop_engine.prune()
        else:
            self.loop_engine.prune(max_age)

    # ---------- آمار ----------
    def stats(self) -> dict:
        return self.stats_engine.stats()


__all__ = ["DB", "SCHEMA", "VALID_MODES"]
