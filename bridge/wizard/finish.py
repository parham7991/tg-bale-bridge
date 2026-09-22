"""FinishEngine — پایان نصب: بررسی کامل بودن + ری‌استارت خودکار برنامه."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("bridge.wizard.finish")

ROOT = Path(__file__).resolve().parents[2]


class FinishEngine:
    """اتمام نصب — اگر ناقص بماند فهرست کمبودها را می‌دهد؛ وگرنه execv."""

    def __init__(self, wiz: Any, store: Any, cfg: Any) -> None:
        self.wiz = wiz
        self.store = store
        self.cfg = cfg

    async def finish(self, chat_id) -> None:
        self.store.set("install_done_at", int(time.time()))
        if not self.store.installed(self.cfg):
            missing = []
            if not self.store.has_tg(self.cfg):
                missing.append("سلف تلگرام (دکمه 📱)")
            if not self.store.has_bale(self.cfg):
                missing.append("سمت بله (دکمه 🟡 یا 🤖)")
            await self.wiz._send(chat_id,
                                 "هنوز کامل نشده:\n" + "\n".join(f"▫️ {m}" for m in missing)
                                 + "\n\nیا اگر همه‌چیز را در .env دارید، فقط ری‌استارت کنید.",
                                 self.wiz._menu_kb())
            return
        await self.wiz._send(chat_id,
                             "🎉 نصب کامل شد! برنامه در حال ری‌استارت برای بالا آمدن پل…\n"
                             "بعد از چند ثانیه /status بزنید.")
        asyncio.create_task(self.do_restart())

    @staticmethod
    async def do_restart() -> None:
        await asyncio.sleep(2)
        logger.warning("ری‌استارت خودکار بعد از نصب…")
        os.execv(sys.executable, [sys.executable, str(ROOT / "main.py")])
