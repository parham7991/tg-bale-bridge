"""بستهٔ سلف تلگرام — تمام منطق سمت Telethon، تفکیک‌شده به ماژول‌ها و موتورها.

معماری (هر بخش، یک ماژول و یک موتور):
    types_map.py → نگاشت‌های خالص: ذخیره‌شده‌ها، متن، فوروارد
    session.py   → TgSelfSession: ساخت/اتصال کلاینت Telethon
    gateway.py   → TgSelfGateway: اعتبارنامه، کلاینت آماده، پروب دسترسی، یوزرنیم
    login.py     → TgLoginEngine: ورود دومرحله‌ای + رمز دوم (ویزارد)
    routing.py   → TgEventRouter: ذخیره‌شده‌ها=پنل، بقیه=پل
    events.py    → TgEventsEngine: ثبت هندلرهای Telethon
    facade.py    → TgSelfBot + register(): ریشهٔ ترکیب — همان سطح عمومی همیشه‌سبز

سازگاری: ``bridge/tg_user.py`` شیم باز-صادرات است؛ همه‌چیز از ``bridge.tguser`` در دسترس است.
"""
from .events import TgEventsEngine
from .facade import TgSelfBot, register
from .gateway import TgSelfGateway
from .login import TgLoginEngine
from .routing import TgEventRouter
from .session import TgSelfSession
from .types_map import has_forward, is_saved_messages, text_of
from .version import VERSION

__all__ = [
    "TgSelfBot", "register", "TgEventRouter", "TgEventsEngine",
    "TgSelfSession", "TgSelfGateway", "TgLoginEngine",
    "is_saved_messages", "text_of", "has_forward", "VERSION",
]
