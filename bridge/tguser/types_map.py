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


def text_of(msg: Any) -> str:
    return (msg.message or "").strip() if msg.message else ""


def has_forward(msg: Any) -> bool:
    return bool(getattr(msg, "forward", None))
