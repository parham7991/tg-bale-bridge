"""نگاشت‌ها و ثابت‌های خالص ویزارد — بدون شبکه و بدون وضعیت.

کیبورد جهت، استخراج اطلاعات فوروارد و استخراج توکن از متن.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

# کیبورد انتخاب جهت همگام‌سازی
DIR_KB = {"inline_keyboard": [[
    {"text": "↔ دوطرفه", "callback_data": "wiz:dir:both"},
    {"text": "تلگرام→بله", "callback_data": "wiz:dir:tg2bale"},
    {"text": "بله→تلگرام", "callback_data": "wiz:dir:bale2tg"},
]]}

# متن‌های پرامپت ورودی‌ها
PROMPT_TG = ("📱 نصب سلف تلگرام — سه مرحله:\n"
             "۱) api_id را بفرستید (از my.telegram.org → API development tools):\n"
             "💡 اگر از قبل در .env گذاشته‌اید، همان را دوباره بفرستید.")
PROMPT_BALE = "🟡 نصب سلف بله:\nشماره تلفن بله را بفرستید (مثلاً +98912...)"
PROMPT_BBOT = "🤖 توکن ربات بله را بفرستید (از @botfather بله — عدد:AA...)"


def forward_chat_info(msg: Optional[dict]) -> Optional[Dict[str, Any]]:
    """اطلاعات کانالِ مبدأ از یک پیام فورواردی (هر دو شکل قدیم/جدید Bot-API)."""
    fwd = (msg or {}).get("forward_from_chat") or {}
    origin = (msg or {}).get("forward_origin") or {}
    if not fwd and origin.get("type") == "chat":
        fwd = {"id": origin.get("chat", {}).get("id"),
               "title": origin.get("chat", {}).get("title"),
               "username": origin.get("chat", {}).get("username")}
    if fwd and fwd.get("id"):
        return {"id": int(fwd["id"]), "title": fwd.get("title") or "",
                "username": (fwd.get("username") or "")}
    return None


def extract_token(text: str) -> str:
    """توکن از متن: اگر فاصله داشت، آخرین تکهٔ حاوی «:»."""
    text = (text or "").strip()
    return text.split()[-1] if ":" in text else text
