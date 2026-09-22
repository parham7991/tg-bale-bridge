"""ClaimEngine — ادمین خودکار: اولین «/start» صاحب بات می‌شود.

تا وقتی ADMIN_TG_ID خالی است و فروشگاه فعال است، هر پیام اینجا بسته می‌شود:
    • متن شروع + قابل‌ادعا → claim در store + تنظیم cfg + خوش‌آمد + بازکردن ویزارد
    • هر پیام دیگر (یا باتِ صاحب‌دار) → پیام 🔒
"""
from __future__ import annotations

import logging
from typing import Any

from .types_map import OWNER_LOCKED_MSG, START_TEXTS

logger = logging.getLogger("bridge.tgbot.claim")


class ClaimEngine:
    """پذیرش ادمین اول — فقط تا اولین صاحب."""

    def __init__(self, api: Any, cfg: Any, store: Any = None,
                 wizard: Any = None) -> None:
        self.api = api
        self.cfg = cfg
        self.store = store
        self.wizard = wizard

    def applicable(self) -> bool:
        """فقط وقتی ادمی در کار نیست و فروشگاه برای claim در دسترس است."""
        return not getattr(self.cfg, "ADMIN_TG_ID", 0) and self.store is not None

    async def handle(self, chat_id, uid, username: str, text: str) -> bool:
        """پردازش در حالت بدون‌ادمین؛ True یعنی پیام بسته شد (ادمین شد یا رد شد)."""
        if not self.applicable():
            return False
        text = (text or "").strip()
        if text in START_TEXTS and self.store.claim_admin(uid, username):
            self.cfg.ADMIN_TG_ID = int(uid)
            logger.info("ادمین خودکار: id=%s (@%s)", uid, username)
            await self.api.send_message(
                chat_id,
                f"✅ خوش آمدید! شما ادمین پل شدید (@{username or uid}).\n"
                "ویزارد نصب را باز می‌کنم…")
            if self.wizard is not None:
                await self.wizard.open(chat_id, uid)
        else:
            await self.api.send_message(chat_id, OWNER_LOCKED_MSG)
        return True
