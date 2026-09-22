"""LifecycleEngine — صف وظایف اجرا + پاک‌سازی نهایی (ترتیب دقیقِ قبل)."""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger("bridge.runtime.lifecycle")


class LifecycleEngine:
    """gather وظایف تا قطع + بستن همهٔ کلاینت‌ها در finally."""

    def __init__(self, cfg, db) -> None:
        self.cfg = cfg
        self.db = db

    def build_tasks(self, tg, bale, bridge, router,
                    tg_bot_task=None, bale_bot_api=None) -> list:
        offset_raw = self.db.get_meta("bale_offset")
        offset = int(offset_raw) if offset_raw else None
        tasks = [
            tg.run_until_disconnected(),
            bale.listen(router.handle_update, offset=offset,
                        timeout=self.cfg.BALE_POLL_TIMEOUT),
            *bridge.workers(),
        ]
        if tg_bot_task:
            tasks.append(tg_bot_task)
        if bale_bot_api:
            bot_offset_raw = self.db.get_meta("bale_bot_offset")
            bot_offset = int(bot_offset_raw) if bot_offset_raw else None
            tasks.append(bale_bot_api.listen(
                router.panel_handler(bale_bot_api), offset=bot_offset,
                timeout=self.cfg.BALE_POLL_TIMEOUT))
        return tasks

    async def run_all(self, tasks, dash=None, tg_bot_api=None, bale_bot_api=None,
                      bale=None) -> None:
        logger.info("آماده دریافت پیام‌ها 🚀")
        try:
            await asyncio.gather(*tasks)
        finally:
            if self.cfg.DASH_ENABLED and dash is not None:
                await dash.stop()
            if tg_bot_api:
                await tg_bot_api.close()
            if bale_bot_api:
                await bale_bot_api.close()
            if bale is not None:
                await bale.close()
