"""ControlBotsEngine — بوت‌های کنترلی: بات مدیریت تلگرام + ربات بلهٔ ترکیبی (اختیاری)."""
from __future__ import annotations

import asyncio
import logging

from ..bot_api import BotAPI, BotAPIError

logger = logging.getLogger("bridge.runtime.bots")


class ControlBotsEngine:
    """ساخت/اجرای سطح‌های مدیریتی باتی — نتیجه برای صف وظایف برمی‌گردد."""

    def __init__(self, cfg, db, store) -> None:
        self.cfg = cfg
        self.db = db
        self.store = store

    async def start(self, admin=None):
        """(tg_bot_api, tg_bot_task, bale_bot_api) — هر کدام می‌توانند None باشند."""
        tg_bot_api = None
        tg_bot_task = None
        if self.cfg.TG_BOT_TOKEN:
            tg_bot_api = BotAPI(self.cfg.TG_BOT_TOKEN, self.cfg.TG_BOT_API_BASE)
            try:
                tg_bot_api.me = await tg_bot_api.get_me()
            except BotAPIError as e:
                logger.error("بات مدیریت تلگرام ناموفق — TG_BOT_TOKEN را بررسی کنید: %s",
                             e)
                tg_bot_api = None
            if tg_bot_api:
                from ..tgbot import TgAdminBot
                from ..wizard import Wizard

                wizard = Wizard(tg_bot_api, self.db, self.cfg, self.store, admin=admin)
                tgbot = TgAdminBot(tg_bot_api, admin, self.db, self.cfg,
                                   wizard=wizard, store=self.store)
                tg_bot_task = asyncio.create_task(tgbot.start())
        else:
            logger.info("TG_BOT_TOKEN تنظیم نشده — بات مدیریت تلگرام غیرفعال است")

        # ---------- ربات بله به‌عنوان سطح ادمین در حالت سلف‌بات (ترکیبی، اختیاری) ----------
        bale_bot_api = None
        token = self.cfg.BALE_TOKEN or (self.store.bale_bot() or {}).get("token", "")
        want_panel = self.cfg.BALE_MODE == "user" or bool(self.store.bale_self())
        if want_panel and token:
            bale_bot_api = BotAPI(token, self.cfg.BALE_API_BASE)
            try:
                bale_bot_api.me = await bale_bot_api.get_me()
            except BotAPIError as e:
                logger.error("ربات بله (ترکیبی) ناموفق — BALE_TOKEN را بررسی کنید: %s", e)
                bale_bot_api = None
            if bale_bot_api:
                logger.info("حالت ترکیبی: ربات بله هم فعال — "
                            "پنل ادمین در چت خصوصی ربات هم جواب می‌دهد")
        return tg_bot_api, tg_bot_task, bale_bot_api
