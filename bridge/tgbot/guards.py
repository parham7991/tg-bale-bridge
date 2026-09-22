"""GuardsEngine — نگهبان‌های بات مدیریت: چه کسی ادمین است؟ غیرادمین چه بشنود؟"""
from __future__ import annotations

from typing import Any

from .types_map import OWNER_LOCKED_MSG


class GuardsEngine:
    """تشخیص ادمین + رد کردن غیرادمین — یک منبع برای کل بات."""

    def __init__(self, cfg: Any) -> None:
        self.cfg = cfg

    def is_admin(self, user_id) -> bool:
        return bool(
            getattr(self.cfg, "ADMIN_TG_ID", 0)
            and int(user_id or 0) == int(self.cfg.ADMIN_TG_ID)
        )

    async def refuse(self, api: Any, chat_id) -> None:
        """پیام «صاحب دارد» برای غیرادمین."""
        await api.send_message(chat_id, OWNER_LOCKED_MSG)
