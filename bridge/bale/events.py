"""EventsEngine — دیسپچر aiobale ⇄ آپدیت‌های Bot-API مانند (مخصوصاً «حذف»).

نکتهٔ زنده-تست‌شده: ثبت هندلر aiobale به‌صورت decorator-factory است —
``dp.message()(fn)`` درست است و ``dp.message(fn)`` هندلر را «فیلتر» ثبت می‌کند!
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from aiobale.types import SelectedMessages

from .normalize import NormalizeEngine
from .session import BaleSession
from .types_map import chat_type_name

logger = logging.getLogger("bridge.bale.events")


class EventsEngine:
    def __init__(self, session: BaleSession, normalize: NormalizeEngine) -> None:
        self.s = session
        self.norm = normalize
        self._listen_task: asyncio.Task | None = None

    # ───────────────────────────── ثبت روی دیسپچر ─────────────────────────────
    def register(self) -> None:
        self.s.dp.message()(self.on_message)
        self.s.dp.message_edited()(self.on_edited)
        self.s.dp.message_deleted()(self.on_deleted)

    # ───────────────────────────── هندلرها ─────────────────────────────
    async def on_message(self, msg: Any) -> None:
        await self.s.emit({"message": self.norm.normalize(msg)})

    async def on_edited(self, msg: Any) -> None:
        await self.s.emit({"edited_message": self.norm.normalize(msg)})

    async def on_deleted(self, selected: SelectedMessages | Any) -> None:
        if not selected or not getattr(selected, "ids", None):
            return
        peer = getattr(selected, "peer", None)
        chat_id = int(getattr(peer, "id", 0) or 0)
        ct = self.s.chat_types.get(str(chat_id))
        if ct is None:
            ct = "group" if chat_type_name(getattr(peer, "type", 0)) == "group" else "private"
            self.s.chat_types[str(chat_id)] = ct
        await self.s.emit(
            {
                "deleted_messages": {
                    "chat": {"id": chat_id, "type": ct},
                    "message_ids": [int(i) for i in selected.ids],
                }
            }
        )

    # ───────────────────────────── گوش‌دادن ─────────────────────────────
    async def listen(self, handler: Callable[..., Any], offset: int = 0,
                     timeout: int = 30) -> None:
        """اتصال هندلر پل به جریان رویداد — تا کنسل شدن اجرا می‌ماند."""
        self.s.handler = handler
        self.s.offset = int(offset or 0)
        await self.s.start()
        stop = asyncio.Event()
        try:
            await stop.wait()  # تا gather کنسل شود
        finally:
            await self.s.stop()
