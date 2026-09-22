"""SurfacesEngine — سطوح مدیریتی و حالت‌آگاهی سلف‌بات/ربات.

پنل چهارسطحی (خودچت بله، ربات بله، بات تلگرام، Saved Messages) —
متن‌های وضعیت بر اساس BALE_MODE و توکن‌های موجود ساخته می‌شوند.
"""
from __future__ import annotations


class SurfacesEngine:
    """«الان چه پنل‌هایی فعالی؟» — فقط از روی پیکربندی."""

    def __init__(self, cfg) -> None:
        self.cfg = cfg

    def is_user_mode(self) -> bool:
        return getattr(self.cfg, "BALE_MODE", "bot") == "user"

    def bale_mode_label(self) -> str:
        return "سلف‌بات بله (BALE_MODE=user)" if self.is_user_mode() else "ربات بله"

    def surfaces(self, tg_bot_info) -> str:
        """پنل‌های فعال مدیریتی — همه به یک پنل وصل‌اند."""
        names = []
        if self.is_user_mode():
            names.append("خودچت بله (پیام به خودتان)")
            if getattr(self.cfg, "BALE_TOKEN", ""):
                names.append("ربات بله")
        else:
            names.append("ربات بله")
        if tg_bot_info:
            names.append("بات تلگرام")
        names.append("Saved Messages تلگرام")
        return " + ".join(names)
