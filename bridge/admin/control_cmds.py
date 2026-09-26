"""ControlCommandsEngine — توقف/ادامهٔ همگام‌سازی + پیام آزمایشی روی هر جفت."""
from __future__ import annotations

import logging

from .types_map import parse_pair_id

logger = logging.getLogger("bridge.admin.control")


class ControlCommandsEngine:
    """کنترل زندهٔ پل — حالت pause در متا هم ماندگار می‌شود."""

    def __init__(self, adm) -> None:
        self.adm = adm                  # خواندن زنده — پچ اتریبیوت‌های نما اثر می‌کند

    @property
    def bridge(self):
        return self.adm.bridge

    @property
    def db(self):
        return self.adm.db

    @property
    def bale(self):
        return self.adm.bale

    @property
    def tg(self):
        return self.adm.tg

    async def pause(self, platform, args, msg):
        self.bridge.paused = True
        self.db.set_meta("paused", "1")
        return ("⏸ همگام‌سازی متوقف شد.\n"
                "پیام‌های جدید تا زمان /resume منتقل نمی‌شوند (نگاشت‌های قبلی حفظ می‌شوند).")

    async def resume(self, platform, args, msg):
        self.bridge.paused = False
        self.db.set_meta("paused", "0")
        return "▶️ همگام‌سازی از سر گرفته شد."

    async def test(self, platform, args, msg):
        if not args:
            return "فرمت: /test <شناسه جفت>"
        pid = parse_pair_id(args[0])
        if pid is None:
            return "فرمت: /test <شناسه جفت> — نمونه: /test 1"
        pair = self.db.get_pair(pid)
        if not pair:
            return "چنین جفتی پیدا نشد."
        text = f"✅ تست پل همگام‌سازی — جفت #{pair['id']}"
        done = []
        if pair["mode"] in ("tg2bale", "both"):
            try:
                await self.bale.send_message(pair["bale_chat_id"], text)
                done.append("بله ✔")
            except Exception as e:
                done.append(f"بله ✘ ({e})")
        if pair["mode"] in ("bale2tg", "both"):
            try:
                ent = await self.bridge.b2t.entity(int(pair["tg_chat_id"]))
                m = await self.tg.send_message(ent, text)
                self.db.mark_sent("tg", str(pair["tg_chat_id"]), m.id)
                done.append("تلگرام ✔")
            except Exception as e:
                done.append(f"تلگرام ✘ ({e})")
        return "نتیجه تست: " + " | ".join(done)
