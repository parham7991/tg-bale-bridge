"""TgEventsEngine — اتصال روتر به دیسپچر Telethon (سه رویداد اصلی).

NewMessage / MessageEdited / MessageDeleted — هر خطا بلعیده و لاگ می‌شود
تا سلف هرگز نات‌داون نکند.
"""
from __future__ import annotations

import logging
from typing import Any

from telethon import events

logger = logging.getLogger("bridge.tguser.events")


class TgEventsEngine:
    """ثبت هندلرهای Telethon — تنها جای تماس مستقیم با دیسپچر."""

    def __init__(self, router: Any) -> None:
        self.router = router

    def register(self, client: Any) -> None:
        @client.on(events.NewMessage())
        async def on_new(event):
            try:
                await self.router.on_new(event)
            except Exception:
                logger.exception("NewMessage handler")

        @client.on(events.MessageEdited())
        async def on_edit(event):
            try:
                await self.router.on_edit(event)
            except Exception:
                logger.exception("MessageEdited handler")

        @client.on(events.MessageDeleted())
        async def on_delete(event):
            try:
                await self.router.on_delete(event)
            except Exception:
                logger.exception("MessageDeleted handler")
