"""DeleteSyncEngine — حذف دوطرفه (با سلف‌بات) با مهار پژواک.

تلگرام→بله: اگر سمت بله سلف باشد (has_delete_events)، حذفِ بازتابی بله علامت
خورده تا دوباره به تلگرام برنگردد. بله→تلگرام: حذف معادل در تلگرام.
در هر صورت ردیف نقشه پاک می‌شود.
"""
from __future__ import annotations

import logging

from ..bot_api import BotAPIError

logger = logging.getLogger("bridge.transfer.deletes")


class DeleteSyncEngine:
    """حذفِ پیام‌های قبلاً آینه‌شده — فقط در جفت‌هایی که جهتشان اجازه می‌دهد."""

    def __init__(self, tg, bale, db, guard) -> None:
        self.tg = tg
        self.bale = bale
        self.db = db
        self.guard = guard

    # --------------------------------- بله → تلگرام
    async def process_bale_delete(self, chat_key, ids) -> None:
        """حذف در بله → حذف پیام معادل در تلگرام (حذف دوطرفه، فقط با سلف‌بات)."""
        for mid in ids:
            for o in self.db.other_side("bale", chat_key, mid):
                if o["platform"] != "tg":
                    continue
                pair = self.db.get_pair(o["pair_id"])
                if not pair or pair["mode"] == "tg2bale":
                    continue
                self.guard.suppress("tg", o["chat"], o["msg"])
                try:
                    await self.tg.delete_messages(int(o["chat"]), [int(o["msg"])])
                except Exception as e:
                    self.guard.release("tg", o["chat"], o["msg"])
                    logger.warning("حذف در تلگرام ناموفق: %s", e)
                self.db.remove_map_row(o["row_id"])

    # --------------------------------- تلگرام → بله
    async def process_tg_delete(self, chat_key, ids) -> None:
        for mid in ids:
            for o in self.db.other_side("tg", chat_key, mid):
                if o["platform"] != "bale":
                    continue
                pair = self.db.get_pair(o["pair_id"])
                if not pair or pair["mode"] == "bale2tg":
                    continue
                if getattr(self.bale, "has_delete_events", False):
                    # سلف‌بات رویداد حذف برمی‌گرداند — پژواک را بی‌اثر کن
                    self.guard.suppress("bale", o["chat"], o["msg"])
                try:
                    await self.bale.delete_message(o["chat"], o["msg"])
                except BotAPIError as e:
                    self.guard.release("bale", o["chat"], o["msg"])
                    logger.warning("حذف در بله ناموفق: %s", e)
                self.db.remove_map_row(o["row_id"])
