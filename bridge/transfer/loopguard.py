"""LoopGuard — نگهبان لوپ و پژواک: دفترچهٔ «ارسال‌شده»، اثر انگشت، خاموش‌کردن پژواک.

دو لایهٔ جلوگیری از لوپ:
    ۱) دفترچهٔ was_sent/mark_sent در دیتابیس (پیام‌هایی که خودمان فرستاده‌ایم)
    ۲) اثر انگشت محتوا (fingerprint) برای پیام‌های بدون شناسهٔ قابل‌ردیابی
    ۳) مجموعه‌های ignore برای بی‌اثرکردن پژواکِ حذفِ خودمان (حذف دوطرفه)
"""
from __future__ import annotations

from typing import Any

from .types_map import fingerprint


class LoopGuard:
    """تمام تصمیم‌های «این رویداد مالِ خودمان است؟» در یک‌جا."""

    def __init__(self, db: Any) -> None:
        self.db = db
        self.ignore_tg: set = set()    # (chat_key, msg_id) — حذف‌های خودمان در تلگرام
        self.ignore_bale: set = set()  # (chat_key, msg_id) — حذف‌های خودمان در بله

    # ─────────────────────── دفترچهٔ ارسال‌شده‌ها ───────────────────────
    def seen(self, platform: str, chat: Any, mid: Any) -> bool:
        """آیا این پیام را خودمان قبلاً فرستاده‌ایم؟ (لایهٔ ۱)"""
        return self.db.was_sent(platform, str(chat), mid)

    def mark(self, platform: str, chat: Any, mid: Any) -> None:
        """ثبت پیام ساخته‌شدهٔ ما در دفترچه."""
        self.db.mark_sent(platform, str(chat), mid)

    # ─────────────────────── اثر انگشت محتوا ───────────────────────
    def fp_check(self, platform: str, chat: Any, kind: str, text: str) -> bool:
        """آیا همین محتوا همین‌الان (پنجرهٔ زمانی) از ما رفته؟ (لایهٔ ۲)"""
        return self.db.check_fp(platform, chat, fingerprint(kind, text or ""))

    def fp_add(self, platform: str, chat: Any, kind: str, text: str) -> None:
        self.db.add_fp(platform, chat, fingerprint(kind, text or ""))

    # ─────────────────────── پژواک حذف ───────────────────────
    @staticmethod
    def _set(guard: "LoopGuard", platform: str) -> set:
        return guard.ignore_tg if platform == "tg" else guard.ignore_bale

    def consume(self, platform: str, chat: Any, mid: Any) -> bool:
        """اگر این حذف پژواکِ خودمان بود، بی‌اثرش کن و True بده."""
        s = self._set(self, platform)
        key = (str(chat), int(mid))
        if key in s:
            s.discard(key)
            return True
        return False

    def suppress(self, platform: str, chat: Any, mid: Any) -> None:
        """قبل از حذفِ عمدی: رویداد حذفِ آینده را علامت بزن که پژواک است."""
        self._set(self, platform).add((str(chat), int(mid)))

    def release(self, platform: str, chat: Any, mid: Any) -> None:
        """اگر حذف ناموفق بود، علامت را پس بگیر."""
        self._set(self, platform).discard((str(chat), int(mid)))
