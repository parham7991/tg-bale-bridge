"""TgBotSession — چرخهٔ حیات بات مدیریت تلگرام: هویت، آفست، حلقهٔ listen.

منبع یکتای «شناسایی بات» (get_me) و ماندگاری آفست getUpdates در متادیتا.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("bridge.tgbot.session")

OFFSET_KEY = "tgbot_offset"


class TgBotSession:
    """مالک کلاینت BotAPI بات مدیریت + هویت + آفست."""

    def __init__(self, api: Any, db: Any = None, timeout: int = 30) -> None:
        self.api = api
        self.db = db
        self.timeout = timeout
        self.me: Dict[str, Any] = {}

    # ───────────────────────────── هویت ─────────────────────────────
    async def identify(self) -> Dict[str, Any]:
        """get_me + نگه‌داری نتیجه — یک‌بار در start()."""
        self.me = await self.api.get_me()
        logger.info("بات مدیریت تلگرام: @%s (id=%s)",
                    self.me.get("username"), self.me.get("id"))
        return self.me

    # ───────────────────────────── آفست ─────────────────────────────
    def offset(self) -> Optional[int]:
        """آفست ذخیره‌شده (پس از ری‌استارت ادامه می‌دهد)."""
        raw = self.db.get_meta(OFFSET_KEY) if self.db is not None else None
        return int(raw) if raw else None

    def save_offset(self, offset) -> None:
        if self.db is not None:
            self.db.set_meta(OFFSET_KEY, str(offset))

    # ───────────────────────────── حلقه ─────────────────────────────
    async def listen(self, handler: Callable) -> None:
        """بلوک‌شونده — long polling تا قطع اتصال."""
        await self.api.listen(handler, offset=self.offset(), timeout=self.timeout)
