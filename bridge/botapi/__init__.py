"""بستهٔ کلاینت Bot-API — تمام منطق HTTP مشترک بله/تلگرام، تفکیک‌شده به ماژول‌ها و موتورها.

معماری (هر بخش، یک ماژول و یک موتور):
    types_map.py  → نگاشت‌های خالص: URL، جدول متدهای رسانه، payload آلبوم
    session.py    → BotAPISession: نشست aiohttp تنبل + تایم‌اوت + بستن
    transport.py  → CallEngine: retry، rate-limit (retry_after)، multipart/json + BotAPIError
    methods.py    → MethodsEngine: متدهای پایه (getMe، sendMessage، ویرایش/حذف…)
    sender.py     → SenderEngine: رسانه‌ها + لوکیشن/مخاطب + sendMediaGroup
    files.py      → FilesEngine: getFile + دانلود استریمی
    events.py     → ListenEngine: حلقهٔ long-polling بی‌نهایت
    facade.py     → BotAPI: ریشهٔ ترکیب — همان سطح عمومی همیشه‌سبز

سازگاری: ``bridge/bot_api.py`` شیم باز-صادرات است؛ همه‌چیز از ``bridge.botapi`` در دسترس است.
"""
from .facade import BotAPI
from .transport import BotAPIError
from .version import VERSION

__all__ = ["BotAPI", "BotAPIError", "VERSION"]
