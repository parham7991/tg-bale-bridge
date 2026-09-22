"""BaleEventRouter — مسیریابی رویدادهای بله (قبلاً در main.py بود).

دو جریان:
• سلف بله: کانال/گروه → موتور همگام‌سازی؛ خودچت ادمین → پنل؛ حذف → همگام‌سازی حذف
• حالت ترکیبی: چت خصوصیِ ربات بله → همان پنل ادمین (کانال‌ها فقط از سشن کاربر)
"""
from __future__ import annotations

import logging
from typing import Any, Callable

log = logging.getLogger("bridge.bale.routing")


class BaleEventRouter:
    def __init__(self, db, cfg, bridge=None, admin=None, bale=None) -> None:
        self.db = db
        self.cfg = cfg
        self.bridge = bridge      # موتور همگام‌سازی — در حالت نصاب None
        self.admin = admin        # پنل ادمین — در حالت نصاب None
        self.bale = bale          # کلاینت سمت بله (ارسال پاسخ پنل)

    # ───────────────────────────── جریان سلف ─────────────────────────────
    async def handle_update(self, upd: dict, offset: int) -> None:
        self.db.set_meta("bale_offset", str(offset))
        dm = upd.get("deleted_messages")
        if dm is not None:
            # فقط سلف بله (aiobale) رویداد حذف می‌دهد → حذف بله→تلگرام
            if self.bridge is not None:
                await self.bridge.on_bale_delete(
                    (dm.get("chat") or {}).get("id"), dm.get("message_ids") or [])
            return
        m = upd.get("message") or upd.get("channel_post")
        em = upd.get("edited_message") or upd.get("edited_channel_post")
        if em:
            if self.bridge is not None:
                await self.bridge.queue_bale_edit(em)
            return
        if not m:
            return
        chat = m.get("chat") or {}
        if chat.get("type") == "private":
            await self._panel_message(m, chat, self.bale)
            return
        if self.bridge is not None:
            await self.bridge.queue_bale_msg(m)

    # ───────────────────────────── پنل (خودچت/ربات) ─────────────────────────────
    async def _panel_message(self, m: dict, chat: dict, sender) -> None:
        uid = (m.get("from") or {}).get("id")
        if self.cfg.BALE_MODE == "user":
            # سلف‌بات = حساب انسانی؛ هرگز به ناشناس‌ها پاسخ خودکار نده
            if not self.cfg.ADMIN_BALE_ID or int(uid or 0) != int(self.cfg.ADMIN_BALE_ID):
                return
        if self.admin is None:
            return
        text = m.get("text") or ""
        is_forward = bool(m.get("forward_from_chat") or m.get("forward_from"))
        if not (text.strip() or is_forward):
            return
        reply = await self.admin.handle("bale", chat.get("id"), uid, text, m)
        if reply and sender is not None:
            await sender.send_message(chat.get("id"), reply)

    # ───────────────────────────── حالت ترکیبی (ربات) ─────────────────────────────
    def panel_handler(self, bale_bot_api) -> Callable[[dict, int], Any]:
        """هندلر چت خصوصی ربات بله در حالت ترکیبی — فقط پنل، بدون دوباره‌کاری کانال."""

        async def _handler(upd: dict, offset: int) -> None:
            self.db.set_meta("bale_bot_offset", str(offset))
            m = upd.get("message")
            if not m:
                return
            chat = m.get("chat") or {}
            if chat.get("type") != "private":
                return  # کانال‌ها فقط از سشن کاربر می‌آیند
            await self._panel_message(m, chat, bale_bot_api)

        return _handler
