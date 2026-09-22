"""EditSyncEngine — همگام‌سازی ویرایش در هر دو جهت.

تلگرام→بله: ویرایش متن یا کپشن با Bot-API؛ در خطا: حذف + ارسال مجدد + جایگزینی نقشه.
بله→تلگرام: ویرایش با Telethon (formatting_entities)؛ در خطا: حذف + ارسال مجدد.
فقط جفت‌هایی که جهتشان ویرایش را شامل می‌شود (mode ≠ معکوس).
"""
from __future__ import annotations

import logging

from .. import formatter as fmt
from ..bot_api import BotAPIError
from .types_map import bale_content, build_entities, tg_kind

logger = logging.getLogger("bridge.transfer.edits")


class EditSyncEngine:
    """ویرایشِ پیام‌های قبلاً آینه‌شده."""

    def __init__(self, tg, bale, db, cfg, t2b, b2t, guard) -> None:
        self.tg = tg
        self.bale = bale
        self.db = db
        self.cfg = cfg
        self.t2b = t2b      # برای جایگزینی (حذف + ارسال مجدد)
        self.b2t = b2t
        self.guard = guard

    # --------------------------------- تلگرام → بله
    async def process_tg_edit(self, msg) -> None:
        chat_key = str(msg.chat_id)
        for o in self.db.other_side("tg", chat_key, msg.id):
            if o["platform"] != "bale":
                continue
            pair = self.db.get_pair(o["pair_id"])
            if not pair or pair["mode"] == "bale2tg":
                continue
            body = fmt.truncate(
                fmt.tg_text_to_bale(msg.message or "", msg.entities),
                self.cfg.LIMIT_TEXT)
            try:
                if tg_kind(msg) in ("text",):
                    await self.bale.edit_message_text(o["chat"], o["msg"], body)
                else:
                    await self.bale.edit_message_caption(o["chat"], o["msg"], body)
            except BotAPIError as e:
                logger.warning("ویرایش در بله ناموفق (%s) — جایگزینی پیام", e)
                try:
                    await self.bale.delete_message(o["chat"], o["msg"])
                    ids = await self.t2b.msg_to_bale(msg, pair["bale_chat_id"], None)
                    if ids:
                        self.db.replace_map_dst(o["row_id"], "bale", str(o["chat"]),
                                                ids[0])
                        self.db.mark_sent("bale", str(o["chat"]), ids[0])
                except Exception:
                    logger.exception("جایگزینی پیام ویرایش‌شده ناموفق")

    # --------------------------------- بله → تلگرام
    async def process_bale_edit(self, m: dict) -> None:
        chat_key = str((m.get("chat") or {}).get("id"))
        c = bale_content(m)
        for o in self.db.other_side("bale", chat_key, m.get("message_id")):
            if o["platform"] != "tg":
                continue
            pair = self.db.get_pair(o["pair_id"])
            if not pair or pair["mode"] == "tg2bale":
                continue
            try:
                entity = await self.b2t.entity(int(o["chat"]))
                tmsg = await self.tg.get_messages(entity, ids=int(o["msg"]))
                if not tmsg:
                    continue
                plain, ents = fmt.bale_text_to_tg(c["text"] or "")
                tg_ents = build_entities(plain, ents)
                try:
                    await tmsg.edit(plain, formatting_entities=tg_ents or None)
                except TypeError:
                    await tmsg.edit(plain)
            except Exception as e:
                logger.warning("ویرایش در تلگرام ناموفق (%s) — جایگزینی پیام", e)
                try:
                    self.guard.suppress("tg", o["chat"], o["msg"])
                    await self.tg.delete_messages(int(o["chat"]), [int(o["msg"])])
                    res = await self.b2t.msg_to_tg(m, int(o["chat"]), None)
                    if res:
                        self.db.replace_map_dst(o["row_id"], "tg", str(o["chat"]),
                                                res[0].id)
                        self.db.mark_sent("tg", str(o["chat"]), res[0].id)
                except Exception:
                    logger.exception("جایگزینی پیام ویرایش‌شده ناموفق")
