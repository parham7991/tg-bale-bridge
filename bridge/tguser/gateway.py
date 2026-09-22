"""TgSelfGateway — دروازهٔ سلف تلگرام: اعتبارنامه، کلاینت آماده، پروب دسترسی.

منبع یکتا برای:
    • آبشار api_id/api_hash (ورودی ویزارد ← .env ← فروشگاه)
    • کلاینت آمادهٔ سلف برای resolve/probe
    • پروب دسترسی (خواندن آخرین پیام کانال)
    • نرمال‌سازی یوزرنیم (‎@user / t.me/user / user)
"""
from __future__ import annotations

import re
from typing import Any, Optional, Tuple


class TgSelfGateway:
    """عملیات سلف تلگرام بدون لاگین — resolve، پروب، اعتبارنامه."""

    @staticmethod
    def resolve_credentials(cfg: Any, store: Any = None,
                            api_id: Any = None, api_hash: Any = None
                            ) -> Tuple[int, str]:
        """آبشار اعتبارنامه: ورودی ویزارد ← cfg (.env) ← فروشگاه (دیتابیس)."""
        saved = (store.tg_api() or {}) if store is not None else {}
        aid = int(api_id or getattr(cfg, "TG_API_ID", 0) or 0) or int(
            saved.get("api_id", 0) or 0)
        ahash = (api_hash or getattr(cfg, "TG_API_HASH", "")
                 or saved.get("api_hash", "") or "")
        return aid, ahash

    @classmethod
    async def ready_client(cls, cfg: Any, store: Any = None) -> Optional[Any]:
        """کلاینت سلف اگر نشست آماده باشد (برای resolve و probe)؛ وگرنه None."""
        if store is not None and not store.has_tg(cfg):
            return None
        aid, ahash = cls.resolve_credentials(cfg, store)
        if not aid or not ahash:
            return None
        from .session import TgSelfSession

        client = TgSelfSession.build(cfg.SESSION_PATH, aid, ahash)
        if not await TgSelfSession.connect_authorized(client):
            return None
        return client

    @staticmethod
    async def probe(tg_client: Any, chat_id: int) -> Tuple[bool, str]:
        """آیا حساب تلگرام به کانال دسترسی دارد؟ (خواندن آخرین پیام)"""
        try:
            try:
                msgs = await tg_client.get_messages(int(chat_id), limit=1)
            except TypeError:
                msgs = await tg_client.get_messages(int(chat_id), ids=1)
            return True, "✔ دسترسی دارد" if msgs is not None else "✔"
        except Exception as e:
            return False, f"✘ {str(e)[:80]}"

    @staticmethod
    def normalize_username(ref: str) -> str:
        """‎@user / https://t.me/user / user → ``user``"""
        ref = (ref or "").strip()
        m = re.search(r"(?:t\.me/|@)([A-Za-z0-9_]{3,})", ref)
        return m.group(1) if m else ref.lstrip("@")
