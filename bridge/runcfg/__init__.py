"""بستهٔ نگارخانهٔ تنظیمات زمان اجرا — تمام منطق store، تفکیک‌شده به ماژول‌ها و موتورها.

معماری (هر بخش، یک ماژول و یک موتور):
    types_map.py  → پیشوند کلیدها + استخراج شناسه ادمین
    kvstore.py    → JsonKVEngine: لایهٔ JSON روی جدول meta
    accounts.py   → AccountsEngine: ادمین خودکار + اکانت‌ها (سلف‌ها/ربات/api)
    readiness.py  → ReadinessEngine: وضعیت نصب هر دو سو
    facade.py     → Store: ریشهٔ ترکیب — همان سطح عمومی همیشه‌سبز

سازگاری: ``bridge/store.py`` شیم باز-صادرات است؛ همه‌چیز از ``bridge.runcfg`` در دسترس است.
"""
from .facade import Store
from .kvstore import JsonKVEngine
from .types_map import PREFIX, admin_id_from, key_of
from .version import VERSION

__all__ = ["Store", "JsonKVEngine", "PREFIX", "key_of", "admin_id_from", "VERSION"]
