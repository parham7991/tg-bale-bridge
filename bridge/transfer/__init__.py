"""بستهٔ همگام‌سازی — قلب پل: تمام منطق آینه‌سازی تلگرام ⇄ بله.

معماری (هر بخش، یک ماژول و یک موتور):
    types_map.py  → نگاشت‌های خالص: کلاه‌بندی پیام، محتوای بله، موجودیت‌ها، اثر انگشت
    loopguard.py  → LoopGuard: دفترچهٔ ارسال‌شده، اثر انگشت، مهار پژواک حذف
    albums.py     → AlbumCollector: گروه‌بندی آلبوم با تایمر flush
    queueing.py   → QueueEngine: دو FIFO قطعی + کارگرها + توقف/ادامه
    mirror_t2b.py → T2BEngine: تلگرام→بله (هر نوع رسانه + فالبک‌ها + آلبوم)
    mirror_b2t.py → B2TEngine: بله→تلگرام (موجودیت‌ها + سقف دانلود + آلبوم)
    sync_edit.py  → EditSyncEngine: ویرایش دوطرفه با جایگزینی در خطا
    sync_delete.py→ DeleteSyncEngine: حذف دوطرفه با مهار پژواک
    facade.py     → Bridge: ریشهٔ ترکیب — همان سطح عمومی همیشه‌سبز

سازگاری: ``bridge/transfer.py`` شیم باز-صادرات است؛ همه‌چیز از ``bridge.transfer`` در دسترس است.
"""
from .facade import Bridge
from .loopguard import LoopGuard
from .mirror_b2t import B2TEngine
from .mirror_t2b import T2BEngine
from .queueing import QueueEngine
from .sync_delete import DeleteSyncEngine
from .sync_edit import EditSyncEngine
from .types_map import (  # noqa: F401 — نام تاریخی _fp بیرون استفاده می‌شود
    GROUPABLE,
    MEDIA_KINDS,
    _fp,
    bale_content,
    build_entities,
    fingerprint,
    tg_kind,
)
from .version import VERSION

__all__ = [
    "Bridge", "QueueEngine", "AlbumCollector", "LoopGuard",
    "T2BEngine", "B2TEngine", "EditSyncEngine", "DeleteSyncEngine",
    "MEDIA_KINDS", "GROUPABLE", "fingerprint", "_fp",
    "tg_kind", "bale_content", "build_entities", "VERSION",
]
