"""InstallerEngine — حالت نصاب: فقط بات کنترل + ویزارد نصب (+ داشبورد اختیاری)."""
from __future__ import annotations

import logging
import sys
import time

from ..bot_api import BotAPI, BotAPIError
from ..dashboard import Dashboard
from ..logbuf import install as install_logbuf
from ..tgbot import TgAdminBot
from ..wizard import Wizard

logger = logging.getLogger("bridge.runtime.installer")


class InstallerEngine:
    """بوت سبک — همه‌چیز از طریق ویزارد ست می‌شود و برنامه خودش ری‌استارت می‌شود."""

    def __init__(self, cfg, db, store) -> None:
        self.cfg = cfg
        self.db = db
        self.store = store

    async def run(self) -> None:
        if not self.cfg.TG_BOT_TOKEN:
            logger.error("TG_BOT_TOKEN در .env لازم است — فقط همین یکی!")
            sys.exit(1)
        logger.warning("نصب ناقص است — حالت نصاب: در بات تلگرام /start بزنید "
                       "و ویزارد را کامل کنید")
        log_handler = install_logbuf()
        started_at = time.time()
        api = BotAPI(self.cfg.TG_BOT_TOKEN, self.cfg.TG_BOT_API_BASE)
        try:
            api.me = await api.get_me()
        except BotAPIError as e:
            logger.error("بات مدیریت تلگرام ناموفق — TG_BOT_TOKEN را بررسی کنید: %s", e)
            sys.exit(1)
        wizard = Wizard(api, self.db, self.cfg, self.store)
        bot = TgAdminBot(api, None, self.db, self.cfg, wizard=wizard,
                         store=self.store)
        dash = Dashboard(self.db, self.store, self.cfg,
                         {"log_buffer": log_handler, "started_at": started_at})
        if self.cfg.DASH_ENABLED:
            await dash.start()
        try:
            await bot.start()
        finally:
            if self.cfg.DASH_ENABLED:
                await dash.stop()
            await api.close()
