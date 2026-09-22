"""WiringEngine — ساخت اجزای پل در حالت کامل: سمت بله، سمت تلگرام، پل+ادمین، داشبورد."""
from __future__ import annotations

import logging
import sys

from ..bot_api import BotAPI, BotAPIError
from ..dashboard import Dashboard
from ..tguser import TgSelfSession
from ..transfer import Bridge

logger = logging.getLogger("bridge.runtime.wiring")


class WiringEngine:
    """هر سازنده یک متد — ترتیب دقیقاً مثل main قدیمی."""

    def __init__(self, cfg, db, store) -> None:
        self.cfg = cfg
        self.db = db
        self.store = store

    # ───────────────────────────── سمت بله ─────────────────────────────
    async def bale_side(self):
        """سلف (aiobale) یا ربات (BotAPI) + get_me + ادمین خودکار خودچت."""
        if self.cfg.BALE_MODE == "user" or self.store.bale_self():
            from ..bale import BaleUserAPI

            bale = BaleUserAPI(
                session_file=self.cfg.BALE_SESSION,
                phone_number=self.cfg.BALE_PHONE or None, db=self.db)
            logger.info("حالت بله: سلف‌بات (حساب کاربری) با aiobale — "
                        "بدون نیاز به اد کردن ربات")
        else:
            bale = BotAPI(self.cfg.BALE_TOKEN, self.cfg.BALE_API_BASE)

        try:
            bale_me = await bale.get_me()
        except BotAPIError as e:
            logger.error("اتصال به بله ناموفق — توکن/نشست را بررسی کنید: %s", e)
            sys.exit(1)
        label = "حساب بله (سلف)" if self.cfg.BALE_MODE == "user" else "ربات بله"
        logger.info("%s: @%s (id=%s)", label, bale_me.get("username"), bale_me.get("id"))

        if self.cfg.BALE_MODE == "user" and not self.cfg.ADMIN_BALE_ID:
            # پنل ادمین بله بدون هیچ تنظیمی: در بله به خودتان پیام بدهید
            self.cfg.ADMIN_BALE_ID = int(bale_me.get("id") or 0)
            logger.info("ADMIN_BALE_ID خودکار = %s (خودتان) — "
                        "در بله به خودتان /help بدهید", self.cfg.ADMIN_BALE_ID)
        return bale, bale_me

    # ───────────────────────────── سمت تلگرام ─────────────────────────────
    async def tg_side(self):
        tg = TgSelfSession.build(self.cfg.SESSION_PATH,
                                 self.cfg.TG_API_ID, self.cfg.TG_API_HASH)
        await tg.start(phone=self.cfg.TG_PHONE or None)
        me = await tg.get_me()
        logger.info("حساب تلگرام (سلف): %s (id=%s)", me.username or me.first_name, me.id)
        return tg, me

    # ───────────────────────────── پل + ادمین + داشبورد ─────────────────────────────
    def bridge_and_admin(self, tg, me, bale, bale_me, log_handler, started_at):
        from ..admin import Admin

        bridge = Bridge(tg, bale, self.db, self.cfg, me.id, bale_me)
        bridge.paused = self.db.get_meta("paused") == "1"
        if bridge.paused:
            logger.warning("⏸ همگام‌سازی از قبل متوقف است (با /resume روشن کنید)")
        admin = Admin(self.db, bale, tg, bridge, self.cfg,
                      log_buffer=log_handler, started_at=started_at)
        return bridge, admin

    def dashboard(self, admin, bridge, tg, bale, me, bale_me,
                  log_handler, started_at) -> Dashboard:
        return Dashboard(self.db, self.store, self.cfg, {
            "admin": admin, "bridge": bridge, "tg": tg, "bale": bale,
            "tg_me": {"id": me.id, "username": me.username,
                      "first_name": me.first_name},
            "bale_me": bale_me,
            "log_buffer": log_handler, "started_at": started_at,
        })
