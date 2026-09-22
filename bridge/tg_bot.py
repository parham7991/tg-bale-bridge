"""بات مدیریت تلگرام — کنترل سلف‌بات از راه دور با Bot API (long-polling)."""
from __future__ import annotations

import logging

log = logging.getLogger("tgbot")


class TgAdminBot:
    """بات تلگرامی برای مدیریت پل: دستورات ادمین + کشف شناسه چت‌ها با فوروارد پیام."""

    def __init__(self, api, admin, db, cfg):
        self.api = api          # BotAPI متصل به api.telegram.org
        self.admin = admin
        self.db = db
        self.cfg = cfg
        self.me: dict = {}

    async def start(self):
        self.me = await self.api.get_me()
        self.admin.tg_bot_info = self.me
        log.info("بات مدیریت تلگرام: @%s (id=%s)",
                 self.me.get("username"), self.me.get("id"))
        if not getattr(self.cfg, "ADMIN_TG_ID", 0):
            log.warning("ADMIN_TG_ID تنظیم نشده — برای فعال‌سازی، در بات تلگرام /start بزنید")
        offset_raw = self.db.get_meta("tgbot_offset")
        offset = int(offset_raw) if offset_raw else None
        await self.api.listen(self.on_update, offset=offset, timeout=30)

    async def on_update(self, upd, offset):
        self.db.set_meta("tgbot_offset", str(offset))
        try:
            m = upd.get("message")
            if not m:
                return
            chat = m.get("chat") or {}
            if chat.get("type") != "private":
                return
            uid = (m.get("from") or {}).get("id")
            text = m.get("text") or ""
            is_forward = bool(
                m.get("forward_from_chat") or m.get("forward_from") or m.get("forward_origin")
            )
            if not text.strip() and not is_forward:
                return
            reply = await self.admin.handle("tgbot", chat.get("id"), uid, text, m)
            if reply:
                await self.api.send_message(chat.get("id"), reply)
        except Exception:
            log.exception("خطا در پردازش آپدیت بات مدیریت")
