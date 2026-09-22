"""TgSelfSession — ساخت و نگه‌داری کلاینت سلف تلگرام (Telethon).

منبع یکتای ساخت کلاینت از روی مسیر نشست + api_id/api_hash؛
هم برای اجرای اصلی (main.py) و هم برای موتور ورود.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("bridge.tguser.session")


class TgSelfSession:
    """مالک کلاینت Telethon سلف."""

    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client

    @staticmethod
    def build(session_path: Any, api_id: Any, api_hash: str) -> Any:
        """کلاینت Telethon از روی مسیر نشست — telethon خودش پسوند .session می‌گذارد."""
        from telethon import TelegramClient

        return TelegramClient(str(session_path), api_id, api_hash)

    @staticmethod
    async def connect_authorized(client: Any) -> bool:
        """اتصال + بررسی مجوز — بدون پرتاب خطا در قطعی شبکه."""
        try:
            await client.connect()
            return bool(await client.is_user_authorized())
        except Exception as e:
            logger.warning("اتصال سلف تلگرام ناموفق: %s", e)
            return False
