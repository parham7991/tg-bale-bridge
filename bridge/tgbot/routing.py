"""TgBotEventRouter — مسیریابی همهٔ رویدادهای بات مدیریت تلگرام، به ترتیب اولویت:

    callback_query → ویزارد (دکمه‌های شیشه‌ای)
    message:
        بدون ادمین            → ClaimEngine (ادمین خودکار / پیام 🔒)
        متن شروع/نصبِ ادمین    → بازکردن ویزارد
        ویزارد فعالِ ادمین     → ادامهٔ مکالمهٔ نصب
        /start غیرادمین       → پیام 🔒
        بقیه                  → پنل ادمین (platform="tgbot")

فقط چت خصوصی پردازش می‌شود؛ فوروارد هم پذیرفته می‌شود (کشف شناسه).
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from .claim import ClaimEngine
from .guards import GuardsEngine
from .types_map import (
    SETUP_TEXTS,
    START_TEXTS,
    chat_id_of,
    is_forward,
    is_private,
    text_of,
    uid_of,
    username_of,
)

logger = logging.getLogger("bridge.tgbot.routing")


class TgBotEventRouter:
    """روتر رویدادهای بات مدیریت — تمام تصمیم‌های «این پیام مال کیست؟»"""

    def __init__(self, api: Any, admin: Any = None, db: Any = None, cfg: Any = None,
                 wizard: Any = None, store: Any = None, session: Any = None) -> None:
        self.api = api
        self.admin = admin      # ممکن است در حالت نصاب None باشد
        self.db = db
        self.cfg = cfg
        self.wizard = wizard
        self.store = store
        self.session = session
        self.claim = ClaimEngine(api, cfg, store, wizard=wizard)
        self.guards = GuardsEngine(cfg)

    # ───────────────────────────── روتیــن ─────────────────────────────
    async def on_update(self, upd: Dict[str, Any], offset) -> None:
        if self.session is not None:
            self.session.save_offset(offset)
        try:
            # ---------- دکمه‌های شیشه‌ای ویزارد ----------
            cb = upd.get("callback_query")
            if cb and self.wizard is not None:
                await self.wizard.handle_callback(cb)
                return

            m = upd.get("message")
            if not m or not is_private(m):
                return
            text = text_of(m)
            uid = uid_of(m)
            chat_id = chat_id_of(m)
            if not text.strip() and not is_forward(m):
                return

            # ---------- ادمین خودکار: اولین /start ----------
            if await self.claim.handle(chat_id, uid, username_of(m), text):
                return

            # ---------- ویزارد ----------
            if self.wizard is not None and self.guards.is_admin(uid):
                if text.strip() in SETUP_TEXTS:
                    await self.wizard.open(chat_id, uid)
                    return
                if self.wizard.is_active(chat_id):
                    await self.wizard.handle_text(chat_id, uid, text, m)
                    return

            # ---------- /start غیرادمین ----------
            if text.strip() in START_TEXTS and not self.guards.is_admin(uid):
                await self.guards.refuse(self.api, chat_id)
                return

            # ---------- پنل ادمین ----------
            if self.admin is None:
                return
            reply = await self.admin.handle("tgbot", chat_id, uid, text, m)
            if reply:
                await self.api.send_message(chat_id, reply)
        except Exception:
            logger.exception("خطا در پردازش آپدیت بات مدیریت")
