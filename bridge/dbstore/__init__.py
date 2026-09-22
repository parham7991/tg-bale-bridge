"""بستهٔ لایهٔ داده — تمام منطق ذخیره‌سازی، تفکیک‌شده به ماژول‌ها و موتورها.

معماری (هر بخش، یک ماژول و یک موتور):
    types_map.py  → SCHEMA + ثابت‌ها (VALID_MODES، عمر کش)
    connection.py → ConnectionEngine: SQLite + RLock + اجرا/پرس‌وجو
    meta.py       → MetaEngine: کلید/مقدار عمومی
    pairs.py      → PairsEngine: CRUD جفت‌ها + جست‌وجوی جهت‌آگاه
    map.py        → MapEngine: نقشهٔ دوطرفهٔ پیام‌ها
    loopcache.py  → LoopCacheEngine: sent (یک‌بارمصرف) + sent_fp (پنجره‌ای) + prune
    stats.py      → StatsEngine: شمارنده‌های وضعیت
    facade.py     → DB: ریشهٔ ترکیب — همان سطح عمومی همیشه‌سبز

سازگاری: ``bridge/db.py`` شیم باز-صادرات است؛ همه‌چیز از ``bridge.dbstore`` در دسترس است.
"""
from .facade import DB
from .types_map import SCHEMA, VALID_MODES
from .version import VERSION

__all__ = ["DB", "SCHEMA", "VALID_MODES", "VERSION"]
