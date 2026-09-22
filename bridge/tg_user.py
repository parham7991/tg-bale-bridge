"""ثبت هندلرهای تلگرام (Telethon) و مسیریابی رویدادها."""
from __future__ import annotations

import logging

from telethon import events

log = logging.getLogger("tg")


def register(client, bridge, admin, my_tg_id: int):
    @client.on(events.NewMessage())
    async def on_new(event):
        try:
            msg = event.message
            # «پیام‌های ذخیره‌شده» = پنل مدیریت
            if msg.chat_id == my_tg_id:
                text = (msg.message or "").strip()
                if text or getattr(msg, "forward", None):
                    reply = await admin.handle("tg", msg.chat_id, my_tg_id, text, msg)
                    if reply:
                        await client.send_message(msg.chat_id, reply, link_preview=False)
                return
            await bridge.on_tg_new(msg)
        except Exception:
            log.exception("NewMessage handler")

    @client.on(events.MessageEdited())
    async def on_edit(event):
        try:
            msg = event.message
            if msg.chat_id == my_tg_id:
                return
            await bridge.on_tg_edit(msg)
        except Exception:
            log.exception("MessageEdited handler")

    @client.on(events.MessageDeleted())
    async def on_delete(event):
        try:
            if event.chat_id is None:
                return
            if event.chat_id == my_tg_id:
                return
            await bridge.on_tg_delete(event.chat_id, event.deleted_ids or [])
        except Exception:
            log.exception("MessageDeleted handler")
