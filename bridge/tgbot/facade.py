"""TgAdminBot — نمای سازگاری بات مدیریت تلگرام (ریشهٔ ترکیب موتورها).

سطح عمومی دقیقاً مثل قبل: ``TgAdminBot(api, admin, db, cfg, wizard, store)`` با
``start()`` / ``on_update(upd, offset)`` / ``_is_admin`` — اما داخل، هر بخش به
موتور خودش تفویض می‌شود:

    session.py  → TgBotSession   (هویت + آفست + listen)
    routing.py  → TgBotEventRouter  (تمام مسیریابی رویدادها)
    claim.py    → ClaimEngine   (ادمین خودکار)
    guards.py   → GuardsEngine  (ادمین؟ / پیام 🔒)
    types_map.py → کمک‌تابع‌های خالص
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from .routing import TgBotEventRouter
from .session import TgBotSession

logger = logging.getLogger("bridge.tgbot.facade")


class TgAdminBot:
    """بات تلگرامی برای مدیریت پل: دستورات ادمین + ویزارد نصب + کشف شناسه با فوروارد."""

    def __init__(self, api: Any, admin: Any, db: Any, cfg: Any,
                 wizard: Any = None, store: Any = None) -> None:
        self.api = api          # BotAPI متصل به api.telegram.org
        self.admin = admin      # ممکن است در حالت نصاب None باشد
        self.db = db
        self.cfg = cfg
        self.wizard = wizard
        self.store = store
        self.me: Dict[str, Any] = {}
        # ── موتورها ──
        self.session = TgBotSession(api, db)
        self.router = TgBotEventRouter(
            api, admin=admin, db=db, cfg=cfg, wizard=wizard, store=store,
            session=self.session)

    # ───────────────────────────── چرخهٔ حیات ─────────────────────────────
    async def start(self) -> None:
        self.me = await self.session.identify()
        if self.admin is not None:
            self.admin.tg_bot_info = self.me
        if getattr(self.cfg, "ADMIN_TG_ID", 0):
            logger.info("ادمین: id=%s", self.cfg.ADMIN_TG_ID)
        else:
            logger.warning("ادمین تعیین نشده — اولین /start ادمین می‌شود")
        await self.session.listen(self.on_update)

    # ───────────────────────────── رویدادها ─────────────────────────────
    async def on_update(self, upd: Dict[str, Any], offset) -> None:
        """تفویض کامل به روتر — این متد فقط برای سازگاری حفظ شده است."""
        await self.router.on_update(upd, offset)

    # ───────────────────────────── سازگاری ─────────────────────────────
    def _is_admin(self, user_id) -> bool:
        return self.router.guards.is_admin(user_id)
