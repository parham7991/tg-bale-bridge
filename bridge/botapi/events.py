"""ListenEngine — حلقهٔ long-polling بی‌نهایت روی getUpdates.

شروع: اگر آفست نبود، انتهای صف فعلی گرفته می‌شود (رد کردن انباشت قدیمی).
هر خطای شبکه/سرور ۵ ثانیه صبر می‌کند و ادامه می‌دهد؛ خطای هندلر کاربر
بلعیده و لاگ می‌شود — حلقه هرگز نمی‌میرد.
"""
from __future__ import annotations

import asyncio
import logging

import aiohttp

from .transport import BotAPIError

logger = logging.getLogger("bridge.botapi.listen")

ERROR_SLEEP = 5


class ListenEngine:
    """حلقهٔ دریافت آپدیت — مصرف‌کنندهٔ api.get_updates."""

    def __init__(self, api) -> None:
        self.api = api

    async def listen(self, handler, offset: int | None = None, timeout: int = 30):
        """long-polling بی‌نهایت؛ handler(update, offset) باید coroutine باشد."""
        if offset is None:
            # رد کردن انباشت قدیمی: گرفتن انتهای صف
            pending = await self.api.get_updates(offset=-1, timeout=0)
            if pending:
                offset = pending[-1]["update_id"] + 1
            else:
                offset = 0
        while True:
            try:
                updates = await self.api.get_updates(offset=offset, timeout=timeout)
            except BotAPIError as e:
                logger.error("getUpdates failed: %s", e)
                await asyncio.sleep(ERROR_SLEEP)
                continue
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.error("getUpdates network error: %s", e)
                await asyncio.sleep(ERROR_SLEEP)
                continue
            for upd in updates or []:
                offset = max(offset, upd["update_id"] + 1)
                try:
                    await handler(upd, offset)
                except Exception:
                    logger.exception("handler error")
