"""AccountsEngine — ساخت کلاینت‌های سمت بله برای ویزارد + بررسی توکن ربات.

BotAPI ربات بله، سلف بله (BaleUserAPI) و انتخاب هوشمند «هرچه نصب است» برای resolve.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Tuple

from ..bot_api import BotAPI

logger = logging.getLogger("bridge.wizard.accounts")


class AccountsEngine:
    """سازنده‌های API سمت بله — فقط این بخش با توکن‌ها سروکار دارد."""

    def __init__(self, wiz: Any, cfg: Any, store: Any) -> None:
        self.wiz = wiz          # برای پچ‌پذیری در تست‌ها (اتصال دیرهنگام)
        self.cfg = cfg
        self.store = store

    # ───────────────────────────── ربات بله ─────────────────────────────
    def bale_bot_api(self) -> BotAPI | None:
        bb = self.store.bale_bot()
        if not bb:
            return None
        return BotAPI(bb["token"], getattr(self.cfg, "BALE_API_BASE",
                                           "https://tapi.bale.ai"))

    async def check_bale_bot(self, token: str) -> Tuple[bool, Any]:
        """توکن ربات بله واقعاً کار می‌کند؟ (get_me + بستن اتصال)"""
        try:
            api = BotAPI(token, getattr(self.cfg, "BALE_API_BASE",
                                        "https://tapi.bale.ai"))
            me = await asyncio.wait_for(api.get_me(), timeout=20)
            await api.close()
            return True, me
        except Exception as e:
            return False, f"توکن نامعتبر: {str(e)[:100]}"

    # ───────────────────────────── سلف بله ─────────────────────────────
    async def bale_user_api(self):
        if not self.store.bale_self():
            return None
        from ..bale import BaleUserAPI

        api = BaleUserAPI(session_file=self.cfg.BALE_SESSION, db=self.wiz.db)
        try:
            await api.start()
        except Exception as e:
            logger.warning("اتصال سلف بله برای resolve ناموفق: %s", e)
            return None
        return api

    # ───────────────────── هرچه نصب است (برای resolve) ─────────────────────
    async def api_for_setup(self):
        api = await self.wiz._bale_user_api()
        if api is not None:
            return api
        return self.wiz._bale_bot_api()
