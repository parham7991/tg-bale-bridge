"""QueueEngine — دو FIFO (تلگرام→بله، بله→تلگرام) + کارگرها + نقطه‌های ورود رویداد.

ترتیب رویدادها با دو صف مجزا قطعی می‌ماند؛ کارگر هر صف جدا است تا کندیِ یک سمت،
سمت دیگر را قفل نکند. هندلرهای هر kind از بیرون تزریق می‌شوند (mirror/edit/delete).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Callable, Dict

from ..tguser.types_map import bare_chat_id
from .albums import AlbumCollector
from .loopguard import LoopGuard

logger = logging.getLogger("bridge.transfer.queue")


class QueueEngine:
    """مالک صف‌ها، کارگرها، وضعیت توقف و نقطه‌های ورود رویدادها."""

    def __init__(self, guard: LoopGuard, albums_tg: AlbumCollector,
                 albums_bale: AlbumCollector) -> None:
        self.guard = guard
        self.albums_tg = albums_tg
        self.albums_bale = albums_bale
        self.q_tg: asyncio.Queue = asyncio.Queue()
        self.q_bale: asyncio.Queue = asyncio.Queue()
        self.paused = False
        # kind → async fn(payload) — توسط facade سیم‌کشی می‌شود
        self.tg_handlers: Dict[str, Callable] = {}
        self.bale_handlers: Dict[str, Callable] = {}

    # ───────────────────────────── کارگرها ─────────────────────────────
    def workers(self):
        return [self._worker(self.q_tg, self.tg_handlers, "تلگرام"),
                self._worker(self.q_bale, self.bale_handlers, "بله")]

    async def _worker(self, q: asyncio.Queue, handlers: Dict[str, Callable],
                      label: str) -> None:
        while True:
            job = await q.get()
            try:
                kind, payload = job
                if self.paused:
                    logger.debug("⏸ همگام‌سازی متوقف است — رویداد %s نادیده گرفته شد",
                                 kind)
                    continue
                h = handlers.get(kind)
                if h is not None:
                    if kind == "delete":
                        await h(payload[0], payload[1])   # (chat_key, ids)
                    else:
                        await h(payload)
            except Exception:
                logger.exception("خطا در پردازش رویداد %s", label)

    # ───────────────────── ورودی‌ها: سمت تلگرام ─────────────────────
    # نکته: رویداد Telethon شناسهٔ کانال را نشان‌دار (-100…) می‌دهد؛ همهٔ کلیدها
    # در پل/دیتابیس خالص‌اند → ورودی را با bare_chat_id نرمال می‌کنیم.
    async def on_tg_new(self, msg) -> None:
        chat_key = str(bare_chat_id(msg.chat_id))
        if self.guard.seen("tg", chat_key, msg.id):
            return
        if msg.grouped_id:
            self.albums_tg.feed((chat_key, msg.grouped_id), msg)
            return
        await self.q_tg.put(("new", [msg]))

    async def on_tg_edit(self, msg) -> None:
        if self.guard.seen("tg", str(bare_chat_id(msg.chat_id)), msg.id):
            return
        await self.q_tg.put(("edit", msg))

    async def on_tg_delete(self, chat_id, deleted_ids) -> None:
        chat_key = str(bare_chat_id(chat_id))
        ids = []
        for mid in deleted_ids:
            if self.guard.consume("tg", chat_key, mid):
                continue
            ids.append(int(mid))
        if ids:
            await self.q_tg.put(("delete", (chat_key, ids)))

    # ───────────────────── ورودی‌ها: سمت بله ─────────────────────
    async def on_bale_delete(self, chat_id, deleted_ids) -> None:
        """حذف پیام در بله — فقط حالت سلف‌بات (aiobale) این رویداد را می‌دهد."""
        chat_key = str(chat_id)
        ids = []
        for mid in deleted_ids or ():
            mid = int(mid)
            if self.guard.consume("bale", chat_key, mid):
                continue
            ids.append(mid)
        if ids:
            await self.q_bale.put(("delete", (chat_key, ids)))

    async def queue_bale_msg(self, m: dict) -> None:
        chat_key = str((m.get("chat") or {}).get("id"))
        if self.guard.seen("bale", chat_key, m.get("message_id")):
            return
        gid = m.get("media_group_id")
        if gid:
            self.albums_bale.feed((chat_key, gid), m)
            return
        await self.q_bale.put(("new", [m]))

    async def queue_bale_edit(self, m: dict) -> None:
        await self.q_bale.put(("edit", m))
