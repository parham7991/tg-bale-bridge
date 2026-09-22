"""نگاشت‌ها و کمک‌تابع‌های خالص بات تلگرام — بدون هیچ وابستگی به شبکه یا کلاس.

متن‌های شروع/نصب، تشخیص چت خصوصی، استخراج فرستنده و تشخیص فوروارد.
"""
from __future__ import annotations

from typing import Any, Dict

# متن‌هایی که «/start» حساب می‌شوند
START_TEXTS = ("/start", "start", "شروع")

# متن‌هایی که ویزارد نصب را باز می‌کنند
SETUP_TEXTS = ("/setup", "setup", "نصب", "/start")

# پیام رد کردن غیرادمین (بات صاحب دارد)
OWNER_LOCKED_MSG = (
    "🔒 این بات قبلاً صاحب دارد. برای انتقال، کلید ADMIN_TG_ID را در .env بگذارید."
)


def chat_of(message: Dict[str, Any]) -> Dict[str, Any]:
    return message.get("chat") or {}


def chat_id_of(message: Dict[str, Any]) -> Any:
    return chat_of(message).get("id")


def is_private(message: Dict[str, Any]) -> bool:
    """فقط چت خصوصی — بات مدیریت هیچ‌وقت در گروه/کانال جواب نمی‌دهد."""
    return chat_of(message).get("type") == "private"


def uid_of(message: Dict[str, Any]) -> Any:
    return (message.get("from") or {}).get("id")


def username_of(message: Dict[str, Any]) -> str:
    return (message.get("from") or {}).get("username") or ""


def text_of(message: Dict[str, Any]) -> str:
    return message.get("text") or ""


def is_forward(message: Dict[str, Any]) -> bool:
    """فوروارد؟ (تلگرام در نسخه‌های مختلف Bot-API سه کلید مختلف می‌دهد)"""
    return bool(
        message.get("forward_from_chat")
        or message.get("forward_from")
        or message.get("forward_origin")
    )
