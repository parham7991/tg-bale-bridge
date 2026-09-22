"""بستهٔ بات تلگرام — تمام منطق بات مدیریت، تفکیک‌شده به ماژول‌ها و موتورها.

معماری (هر بخش، یک ماژول و یک موتور):
    types_map.py → نگاشت‌های خالص: متن‌های شروع/نصب، چت خصوصی، فوروارد
    session.py   → TgBotSession: هویت بات، آفست، حلقهٔ listen
    claim.py     → ClaimEngine: ادمین خودکار (اولین /start)
    guards.py    → GuardsEngine: تشخیص ادمین + پیام 🔒
    routing.py   → TgBotEventRouter: مسیریابی همهٔ رویدادها (ویزارد/ادمین/ادعا)
    facade.py    → TgAdminBot: ریشهٔ ترکیب — همان سطح عمومی همیشه‌سبز

سازگاری: ``bridge/tg_bot.py`` شیم باز-صادرات است؛ همه‌چیز از ``bridge.tgbot`` در دسترس است.
"""
from .facade import TgAdminBot
from .routing import TgBotEventRouter
from .session import TgBotSession
from .types_map import (
    OWNER_LOCKED_MSG,
    SETUP_TEXTS,
    START_TEXTS,
    is_forward,
    is_private,
)
from .version import VERSION

__all__ = [
    "TgAdminBot", "TgBotEventRouter", "TgBotSession",
    "START_TEXTS", "SETUP_TEXTS", "OWNER_LOCKED_MSG", "is_forward", "is_private",
    "VERSION",
]
