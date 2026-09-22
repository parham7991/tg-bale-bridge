"""OverridesEngine — اعمال پیکربندی ذخیره‌شدهٔ ویزارد روی cfg (.env حداقلی).

فقط خانه‌های خالی پر می‌شوند؛ مقدارهای .env همیشه اولویت دارند.
"""
from __future__ import annotations


class OverridesEngine:
    """ترکیب store ← cfg به‌صورت زنده در هر بوت."""

    def __init__(self, store) -> None:
        self.store = store

    def apply(self, cfg) -> None:
        admin = self.store.admin_tg_id()
        if admin and not cfg.ADMIN_TG_ID:
            cfg.ADMIN_TG_ID = admin
        api = self.store.tg_api()
        if api:
            if not cfg.TG_API_ID:
                cfg.TG_API_ID = int(api.get("api_id") or 0)
            if not cfg.TG_API_HASH:
                cfg.TG_API_HASH = api.get("api_hash", "")
        bb = self.store.bale_bot()
        if bb and not cfg.BALE_TOKEN:
            cfg.BALE_TOKEN = bb.get("token", "")
