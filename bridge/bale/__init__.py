"""بستهٔ بله — تمام منطق سمت بله، تفکیک‌شده به ماژول‌ها و موتورها.

معماری (هر بخش، یک ماژول و یک موتور):
    types_map.py   → نگاشت‌های خالص: انواع چت، تشخیص رسانه، بازکردن wrapperها
    session.py     → BaleSession: وضعیت مشترک (کلاینت، کش‌ها، چرخهٔ حیات)
    resolver.py    → ResolverEngine: شناسه/یوزرنیم/نوع چت/ریپلای
    normalize.py   → NormalizeEngine: پیام داخلی بله ⇄ دیکشنری Bot-API
    events.py      → EventsEngine: دیسپچر، رویدادها (از جمله حذف!)، listen
    sender.py      → SenderEngine: همهٔ send_* با فالبک‌های کامل
    editor.py      → EditorEngine: ویرایش متن/کپشن + حذف (با کش تاریخ)
    files.py       → FilesEngine: دانلود/متادیتا با کش access_hash
    admin_ops.py   → AdminOpsEngine: invite + make_user_admin (ادمین‌کردن ربات)
    profile.py     → ProfileEngine: get_me / get_chat
    gateway.py     → BaleBotGateway: موتور «ربات بله» (resolve + پروب دسترسی)
    routing.py     → BaleEventRouter: مسیریابی رویدادهای بله (سلف + پنل ترکیبی)
    facade.py      → BaleUserAPI: ریشهٔ ترکیب — همان سطح عمومی همیشه‌سبز

سازگاری: ``bridge/bale_user.py`` شیم باز-صادرات است؛ همه‌چیز از ``bridge.bale`` در دسترس است.
"""
from .facade import BaleUserAPI
from .gateway import BaleBotGateway
from .routing import BaleEventRouter
from .session import BaleSession
from .types_map import (
    _classify_document,
    classify_document,
    extract_id,
    extract_user,
    unwrap,
)
from .version import VERSION

__all__ = [
    "BaleUserAPI", "BaleBotGateway", "BaleEventRouter", "BaleSession",
    "classify_document", "_classify_document", "extract_id", "extract_user",
    "unwrap", "VERSION",
]
