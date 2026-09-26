"""TgEventRouter — مسیریابی رویدادهای سلف تلگرام.

قاعدهٔ ثابت:
    «پیام‌های ذخیره‌شده» = پنل مدیریت (ادمین) · بقیه = آینه‌سازی (پل)
    ویرایش/حذفِ ذخیره‌شده‌ها نادیده گرفته می‌شود.
"""
from __future__ import annotations

import logging
from typing import Any

from .types_map import bare_chat_id, has_forward, is_saved_messages, text_of

logger = logging.getLogger("bridge.tguser.routing")


class TgEventRouter:
    """تصمیم‌های «این رویداد مال کیست؟» برای سلف تلگرام."""

    def __init__(self, bridge: Any, admin: Any = None, my_tg_id: int = 0) -> None:
        self.bridge = bridge
        self.admin = admin
        self.my_tg_id = int(my_tg_id or 0)

    async def on_new(self, event: Any) -> None:
        msg = event.message
        if is_saved_messages(msg, self.my_tg_id):
            text = text_of(msg)
            if text or has_forward(msg):
                reply = await self.admin.handle("tg", msg.chat_id, self.my_tg_id,
                                                text, msg)
                if reply:
                    client = event.client
                    await client.send_message(msg.chat_id, reply, link_preview=False)
            return
        await self.bridge.on_tg_new(msg)

    async def on_edit(self, event: Any) -> None:
        msg = event.message
        if is_saved_messages(msg, self.my_tg_id):
            return
        await self.bridge.on_tg_edit(msg)

    async def on_delete(self, event: Any) -> None:
        if event.chat_id is None or event.chat_id == self.my_tg_id:
            return
        await self.bridge.on_tg_delete(bare_chat_id(event.chat_id),
                                       event.deleted_ids or [])
