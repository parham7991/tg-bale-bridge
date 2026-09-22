"""AlbumCollector — گروه‌بندی آلبوم‌ها (media group) برای هر دو جهت.

اولین پیامِ گروه، تایمر flush را می‌سازد؛ بقیه فقط اضافه می‌شوند.
پس از سپری‌شدن تأخیر، همه به‌ترتیب شناسه در یک job («new», [msgs]) صف می‌شوند.
تأخیر بله ۱٫۴ برابر است (getUpdates کندتر از رویدادهای Telethon می‌رسد).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, Tuple

logger = logging.getLogger("bridge.transfer.albums")


class AlbumCollector:
    """جمع‌کنندهٔ آلبوم یک جهت — نمونهٔ جدا برای تلگرام و بله."""

    def __init__(self, queue: asyncio.Queue, delay: Callable[[], float],
                 sort_key: Callable[[Any], Any]) -> None:
        self.queue = queue
        self.delay = delay              # callable —cfg در زمان flush خوانده شود
        self.sort_key = sort_key
        self.pending: Dict[Tuple[str, Any], list] = {}
        self.tasks: Dict[Tuple[str, Any], asyncio.Task] = {}

    def feed(self, key: Tuple[str, Any], item: Any) -> None:
        """پیام جدیدِ دارای grouped_id/media_group_id."""
        lst = self.pending.setdefault(key, [])
        lst.append(item)
        if len(lst) == 1:
            self.tasks[key] = asyncio.create_task(self.flush(key))

    async def flush(self, key: Tuple[str, Any]) -> None:
        await asyncio.sleep(self.delay())
        msgs = self.pending.pop(key, [])
        self.tasks.pop(key, None)
        if msgs:
            msgs.sort(key=self.sort_key)
            await self.queue.put(("new", msgs))
