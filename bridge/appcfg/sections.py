"""SectionsEngine — بخش‌های .env: تلگرام، بله، بات کنترل، عمومی، داشبورد."""
from __future__ import annotations

from .envparse import EnvParseEngine


class SectionsEngine:
    """هر بخش یک متد — خروجی dict تخت از کلیدهای پیکربندی."""

    def __init__(self, env: dict | None = None) -> None:
        self.env = env if env is not None else {}
        self.p = EnvParseEngine(self.env)

    # --- تلگرام (سلف) ---
    def tg(self) -> dict:
        return {
            "TG_API_ID": self.p.int_of("TG_API_ID"),
            "TG_API_HASH": self.p.stripped("TG_API_HASH"),
            "TG_PHONE": self.p.stripped("TG_PHONE"),
        }

    # --- بله ---
    def bale(self, data_dir) -> dict:
        return {
            "BALE_TOKEN": self.p.stripped("BALE_TOKEN"),
            "BALE_API_BASE": self.p.stripped("BALE_API_BASE",
                                             "https://tapi.bale.ai").rstrip("/"),
            "ADMIN_BALE_ID": self.p.int_of("ADMIN_BALE_ID"),
            # "bot"  → ربات رسمی بله (برای نوشتن در کانال باید ادمین شود)
            # "user" → سلف‌بات بله (aiobale) — بدون نیاز به اد کردن ربات
            "BALE_MODE": self.p.stripped("BALE_MODE", "bot").lower(),
            "BALE_SESSION": self.p.stripped("BALE_SESSION",
                                            str(data_dir / "session")),
            "BALE_PHONE": self.p.stripped("BALE_PHONE"),
        }

    # --- بات مدیریت تلگرام (اختیاری) ---
    def control(self) -> dict:
        return {
            "TG_BOT_TOKEN": self.p.stripped("TG_BOT_TOKEN"),
            "TG_BOT_API_BASE": self.p.stripped("TG_BOT_API_BASE",
                                               "https://api.telegram.org").rstrip("/"),
            "ADMIN_TG_ID": self.p.int_of("ADMIN_TG_ID"),
        }

    # --- عمومی ---
    def general(self) -> dict:
        return {
            "ALBUM_DELAY": self.p.float_of("ALBUM_DELAY", 0.9),
            "BALE_POLL_TIMEOUT": self.p.int_of("BALE_POLL_TIMEOUT", 30) or 30,
        }

    # --- داشبورد وب ---
    def dash(self) -> dict:
        return {
            "DASH_ENABLED": self.p.flag("DASH_ENABLED", "1"),
            "DASH_HOST": self.p.stripped("DASH_HOST", "0.0.0.0"),
            "DASH_PORT": self.p.int_of("DASH_PORT", 8080) or 8080,
        }
