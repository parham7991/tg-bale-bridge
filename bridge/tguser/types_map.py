"""نگاشت‌ها و کمک‌تابع‌های خالص سلف تلگرام — بدون وابستگی به شبکه.

تشخیص «پیام‌های ذخیره‌شده» (پنل مدیریت)، استخراج متن و تشخیص فوروارد.
"""
from __future__ import annotations

from typing import Any


def is_saved_messages(msg: Any, my_tg_id: int) -> bool:
    """پیام در «پیام‌های ذخیره‌شده» است؟ (= چت پنل مدیریت سلف)"""
    try:
        return msg.chat_id == my_tg_id
    except AttributeError:
        return False


def bare_chat_id(chat_id: Any) -> int:
    """شناسهٔ «نشان‌دار» تلگتون (‎-100…) → شناسهٔ خالص کانال/سوپرگروه.

    رویدادهای Telethon برای کانال‌ها chat_id را به‌شکل ``-100XXXXXXXXXX`` می‌دهند،
    در حالی که جفت‌ها (ویرایش/حذف/صف‌ها) با شناسهٔ خالص ذخیره می‌شوند — این
    نرمال‌سازی جلوی «جفت پیدا نشد»های بی‌صدا را می‌گیرد (باگ زندهٔ v2.17.5).
    """
    try:
        n = int(chat_id)
    except (TypeError, ValueError):
        return 0
    if -1009999999999 <= n <= -1000000000000:
        return -(n + 1000000000000)
    return n


def text_of(msg: Any) -> str:
    return (msg.message or "").strip() if msg.message else ""


def has_forward(msg: Any) -> bool:
    return bool(getattr(msg, "forward", None))
