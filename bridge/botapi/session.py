"""BotAPISession — مالک نشست HTTP (aiohttp): ساخت تنبل، تایم‌اوت، بستن."""
from __future__ import annotations

import logging
from typing import Optional

import aiohttp

logger = logging.getLogger("bridge.botapi.session")

# تایم‌اوت کل ۱۸۰ ثانیه؛ اتصال سوکت ۳۰ ثانیه
TOTAL_TIMEOUT = 180
SOCK_CONNECT_TIMEOUT = 30


class BotAPISession:
    """نشست مشترک همهٔ فراخوانی‌ها — یک نمونه به ازای هر کلاینت."""

    def __init__(self) -> None:
        self.session: Optional[aiohttp.ClientSession] = None

    async def get(self) -> aiohttp.ClientSession:
        """نشست زنده — در صورت بسته‌بودن دوباره ساخته می‌شود."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=TOTAL_TIMEOUT,
                                              sock_connect=SOCK_CONNECT_TIMEOUT)
            )
        return self.session

    async def close(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()
